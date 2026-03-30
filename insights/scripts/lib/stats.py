"""Compute per-session stats from OpenCode database records."""

import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Any

from .labels import EXTENSION_TO_LANGUAGE, TOOL_ERROR_PATTERNS


def _epoch_ms_to_iso(ms: int | None) -> str | None:
    """Convert epoch milliseconds to ISO 8601 string."""
    if ms is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _categorize_tool_error(output: str) -> str:
    """Categorize a tool error by matching output against known patterns."""
    lower = output.lower()
    for category, patterns in TOOL_ERROR_PATTERNS.items():
        for pattern in patterns:
            if pattern in lower:
                return category
    return "Other"


def _extract_language(file_path: str) -> str | None:
    """Extract language from a file path's extension."""
    ext = PurePosixPath(file_path).suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def extract_session_stats(
    session: dict,
    messages: list[dict],
    parts_by_message: dict[str, list[dict]],
) -> dict[str, Any]:
    """Extract all metrics from a single session's data.

    Args:
        session: Row from session table.
        messages: Rows from message table for this session.
        parts_by_message: Parts grouped by message_id.

    Returns:
        Session metadata dict matching the spec schema.
    """
    user_msg_count = 0
    assistant_msg_count = 0
    tool_counts: Counter = Counter()
    languages: Counter = Counter()
    git_commits = 0
    git_pushes = 0
    input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0
    cost = 0.0
    first_prompt = ""
    tool_errors = 0
    tool_error_categories: Counter = Counter()
    uses_task_agent = False
    uses_mcp = False
    uses_web_search = False
    uses_web_fetch = False
    message_hours: list[int] = []
    user_message_timestamps: list[int] = []
    user_response_times: list[float] = []
    agent_counts: Counter = Counter()
    model_counts: Counter = Counter()

    last_assistant_time: int | None = None

    for msg in messages:
        data = msg.get("data", {})
        role = data.get("role", "")
        msg_time = msg.get("time_created")
        parts = parts_by_message.get(msg["id"], [])

        if role == "user":
            # Check if this message has text parts
            has_text = any(
                p.get("data", {}).get("type") == "text" for p in parts
            )
            if has_text:
                user_msg_count += 1
                if msg_time:
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(msg_time / 1000, tz=timezone.utc)
                    message_hours.append(dt.hour)
                    user_message_timestamps.append(msg_time)

                    # Response time: seconds since last assistant message
                    if last_assistant_time is not None:
                        delta = (msg_time - last_assistant_time) / 1000.0
                        if 2.0 < delta < 3600.0:
                            user_response_times.append(round(delta, 3))

                # First prompt
                if not first_prompt:
                    for p in parts:
                        pd = p.get("data", {})
                        if pd.get("type") == "text" and pd.get("text"):
                            first_prompt = pd["text"][:500]
                            break


        elif role == "assistant":
            assistant_msg_count += 1
            if msg_time:
                last_assistant_time = msg_time

            # Tokens
            tokens = data.get("tokens", {})
            input_tokens += tokens.get("input", 0)
            output_tokens += tokens.get("output", 0)
            reasoning_tokens += tokens.get("reasoning", 0)

            # Cost
            cost += data.get("cost", 0) or 0

            # Agent and model tracking
            agent = data.get("agent", "")
            if agent:
                agent_counts[agent] += 1
            model_id = data.get("modelID", "")
            if model_id:
                model_counts[model_id] += 1

        # Process parts for tool stats
        for p in parts:
            pd = p.get("data", {})
            ptype = pd.get("type")

            if ptype == "tool":
                tool_name = pd.get("tool", "unknown")
                tool_counts[tool_name] += 1
                state = pd.get("state", {})

                # Feature flags
                if tool_name == "task":
                    uses_task_agent = True
                elif tool_name == "websearch":
                    uses_web_search = True
                elif tool_name == "webfetch":
                    uses_web_fetch = True
                elif tool_name.startswith("mcp_") or "_" in tool_name and not tool_name.startswith(("ckb_",)):
                    # MCP tools typically have prefix patterns
                    if tool_name not in (
                        "bash", "read", "write", "edit", "grep", "glob",
                        "list", "patch", "question", "todowrite", "todoread",
                        "task", "websearch", "webfetch", "skill", "lsp",
                    ):
                        uses_mcp = True

                # Git detection from bash commands
                if tool_name == "bash":
                    cmd = ""
                    inp = state.get("input", {})
                    if isinstance(inp, dict):
                        cmd = inp.get("command", "")
                    elif isinstance(inp, str):
                        cmd = inp
                    if "git commit" in cmd:
                        git_commits += 1
                    if "git push" in cmd:
                        git_pushes += 1

                # Language detection from edit/write tools
                if tool_name in ("edit", "write"):
                    inp = state.get("input", {})
                    file_path = ""
                    if isinstance(inp, dict):
                        file_path = inp.get("file_path", "") or inp.get("path", "")
                    # Try metadata.path
                    if not file_path:
                        file_path = state.get("metadata", {}).get("path", "")
                    # Try extracting from title (e.g. "Editing /path/to/file.py")
                    if not file_path:
                        title = state.get("title", "")
                        if title:
                            m = re.search(r"(/[\w./\-]+\.\w+)", title)
                            if m:
                                file_path = m.group(1)
                    if file_path:
                        lang = _extract_language(file_path)
                        if lang:
                            languages[lang] += 1

                # Language detection from patch tool
                if tool_name == "patch":
                    for fp in pd.get("files", []):
                        if isinstance(fp, str) and fp:
                            lang = _extract_language(fp)
                            if lang:
                                languages[lang] += 1

                # Tool errors
                status = state.get("status", "")
                if status in ("error", "failed"):
                    tool_errors += 1
                    output = state.get("error", "") or state.get("output", "") or ""
                    if isinstance(output, str):
                        cat = _categorize_tool_error(output)
                        tool_error_categories[cat] += 1

    start_time = session.get("time_created")
    end_time = session.get("time_updated")
    duration_minutes = 0
    if start_time and end_time:
        duration_minutes = round((end_time - start_time) / 60000, 1)

    result = {
        "session_id": session["id"],
        "project_path": session.get("directory", ""),
        "start_time": _epoch_ms_to_iso(start_time),
        "duration_minutes": duration_minutes,
        "user_message_count": user_msg_count,
        "assistant_message_count": assistant_msg_count,
        "tool_counts": dict(tool_counts),
        "languages": dict(languages),
        "git_commits": git_commits,
        "git_pushes": git_pushes,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "first_prompt": first_prompt,
        "user_response_times": user_response_times,
        "tool_errors": tool_errors,
        "tool_error_categories": dict(tool_error_categories),
        "uses_task_agent": uses_task_agent,
        "uses_mcp": uses_mcp,
        "uses_web_search": uses_web_search,
        "uses_web_fetch": uses_web_fetch,
        "lines_added": session.get("summary_additions", 0) or 0,
        "lines_removed": session.get("summary_deletions", 0) or 0,
        "files_modified": session.get("summary_files", 0) or 0,
        "message_hours": message_hours,
        "user_message_timestamps": user_message_timestamps,
        "summary": session.get("title", ""),
        "reasoning_tokens": reasoning_tokens,
        "cost": round(cost, 4),
        "agent_counts": dict(agent_counts),
        "model_counts": dict(model_counts),
    }
    return result


def extract_child_rollup(
    messages: list[dict],
    parts_by_message: dict[str, list[dict]],
) -> dict[str, Any]:
    """Extract rollup-able stats from a child (subagent) session.

    Only extracts metrics that should be merged into the parent:
    agent_counts, tool_counts, tokens, cost, languages, git activity.
    Does NOT extract: tool_errors, response_times, message_hours.
    """
    tool_counts: Counter = Counter()
    languages: Counter = Counter()
    git_commits = 0
    git_pushes = 0
    input_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0
    cost = 0.0
    agent_counts: Counter = Counter()
    model_counts: Counter = Counter()

    for msg in messages:
        data = msg.get("data", {})
        role = data.get("role", "")
        parts = parts_by_message.get(msg["id"], [])

        if role == "assistant":
            tokens = data.get("tokens", {})
            input_tokens += tokens.get("input", 0)
            output_tokens += tokens.get("output", 0)
            reasoning_tokens += tokens.get("reasoning", 0)
            cost += data.get("cost", 0) or 0

            agent = data.get("agent", "")
            if agent:
                agent_counts[agent] += 1
            model_id = data.get("modelID", "")
            if model_id:
                model_counts[model_id] += 1

        for p in parts:
            pd = p.get("data", {})
            ptype = pd.get("type")

            if ptype == "tool":
                tool_name = pd.get("tool", "unknown")
                tool_counts[tool_name] += 1
                state = pd.get("state", {})

                # Git detection
                if tool_name == "bash":
                    cmd = ""
                    inp = state.get("input", {})
                    if isinstance(inp, dict):
                        cmd = inp.get("command", "")
                    elif isinstance(inp, str):
                        cmd = inp
                    if "git commit" in cmd:
                        git_commits += 1
                    if "git push" in cmd:
                        git_pushes += 1

                # Language detection
                if tool_name in ("edit", "write"):
                    inp = state.get("input", {})
                    file_path = ""
                    if isinstance(inp, dict):
                        file_path = inp.get("file_path", "") or inp.get("path", "")
                    if not file_path:
                        file_path = state.get("metadata", {}).get("path", "")
                    if not file_path:
                        title = state.get("title", "")
                        if title:
                            m = re.search(r"(/[\w./\-]+\.\w+)", title)
                            if m:
                                file_path = m.group(1)
                    if file_path:
                        lang = _extract_language(file_path)
                        if lang:
                            languages[lang] += 1

                if tool_name == "patch":
                    for fp in pd.get("files", []):
                        if isinstance(fp, str) and fp:
                            lang = _extract_language(fp)
                            if lang:
                                languages[lang] += 1

    return {
        "tool_counts": dict(tool_counts),
        "languages": dict(languages),
        "git_commits": git_commits,
        "git_pushes": git_pushes,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cost": round(cost, 4),
        "agent_counts": dict(agent_counts),
        "model_counts": dict(model_counts),
    }


def merge_child_rollup(parent_stats: dict, child_rollup: dict) -> None:
    """Merge child session rollup into parent stats in-place.

    agent_counts and model_counts go into separate child_* keys
    so the report can show parent vs subagent usage separately.
    """
    # These merge into parent
    for key in ("tool_counts", "languages"):
        parent = parent_stats.get(key, {})
        for k, v in child_rollup.get(key, {}).items():
            parent[k] = parent.get(k, 0) + v
        parent_stats[key] = parent

    # These go into separate child_* keys
    for key in ("agent_counts", "model_counts"):
        child_key = f"child_{key}"
        child = parent_stats.get(child_key, {})
        for k, v in child_rollup.get(key, {}).items():
            child[k] = child.get(k, 0) + v
        parent_stats[child_key] = child

    for key in ("git_commits", "git_pushes", "input_tokens", "output_tokens", "reasoning_tokens"):
        parent_stats[key] = parent_stats.get(key, 0) + child_rollup.get(key, 0)

    parent_stats["cost"] = round(
        parent_stats.get("cost", 0) + child_rollup.get("cost", 0), 4
    )
