#!/usr/bin/env python3
"""Step 1: Query OpenCode SQLite DB and extract session metadata + transcripts.

Usage:
    python3 extract_sessions.py --db ~/.local/share/opencode/opencode.db --out /tmp/opencode-insights-XXXXX/
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

# Allow imports from lib/
sys.path.insert(0, str(Path(__file__).parent))

from lib.db import connect, fetch_sessions, fetch_messages, fetch_parts_for_messages, fetch_child_sessions
from lib.stats import extract_session_stats, extract_child_rollup, merge_child_rollup
from lib.transcript import serialize_transcript


def _is_self_referential(parts_by_message: dict, messages: list[dict]) -> bool:
    """Check if this session is an insights-generation session itself."""
    user_text_count = 0
    for msg in messages:
        data = msg.get("data", {})
        if data.get("role") != "user":
            continue
        parts = parts_by_message.get(msg["id"], [])
        for p in parts:
            pd = p.get("data", {})
            if pd.get("type") == "text":
                text = pd.get("text", "")
                if "RESPOND WITH ONLY A VALID JSON OBJECT" in text:
                    return True
                if "record_facets" in text:
                    return True
                user_text_count += 1
                if user_text_count >= 5:
                    return False
    return False


def _discover_user_setup(all_meta: list[dict]) -> dict:
    """Discover custom agents, skills, commands, tools across all session project dirs."""
    import glob

    project_dirs = set()
    for m in all_meta:
        p = m.get("project_path", "")
        if p:
            project_dirs.add(p)
    # Also check global config
    global_config = Path.home() / ".config" / "opencode"
    project_dirs.add(str(global_config))

    agents: dict[str, list[str]] = {}   # project -> [agent names]
    skills: dict[str, list[str]] = {}   # project -> [skill names]
    commands: dict[str, list[str]] = {}  # project -> [command names]
    tools: dict[str, list[str]] = {}    # project -> [tool names]
    agents_md: dict[str, str] = {}      # project -> AGENTS.md content (truncated)
    mcp_servers: dict[str, list[str]] = {}  # project -> [server names]
    plugins: dict[str, list[str]] = {}      # project -> [plugin names]
    formatters: dict[str, list[str]] = {}   # project -> [language names]
    permissions: dict[str, dict] = {}       # project -> permission config
    github_actions: dict[str, list[str]] = {}  # project -> [workflow names with opencode]
    opencode_config: dict[str, dict] = {}   # project -> key config values

    for proj in project_dirs:
        proj_path = Path(proj)
        label = proj_path.name if proj_path != global_config else "~global"

        # Agents: .opencode/agents/*.md
        for f in glob.glob(str(proj_path / ".opencode/agents/*.md")):
            agents.setdefault(label, []).append(Path(f).stem)

        # Skills: .opencode/skills/*/SKILL.md
        for f in glob.glob(str(proj_path / ".opencode/skills/*/SKILL.md")):
            skills.setdefault(label, []).append(Path(f).parent.name)

        # Commands: .opencode/commands/*.md
        for pattern in [".opencode/commands/*.md"]:
            for f in glob.glob(str(proj_path / pattern)):
                commands.setdefault(label, []).append(Path(f).stem)

        # Tools: .opencode/tools/*.ts
        for pattern in [".opencode/tools/*.ts", ".opencode/tools/*.js"]:
            for f in glob.glob(str(proj_path / pattern)):
                tools.setdefault(label, []).append(Path(f).stem)

        # Plugins: .opencode/plugins/*.ts/.js
        for pattern in [".opencode/plugins/*.ts", ".opencode/plugins/*.js"]:
            for f in glob.glob(str(proj_path / pattern)):
                plugins.setdefault(label, []).append(Path(f).stem)

        # GitHub Actions referencing opencode
        for f in glob.glob(str(proj_path / ".github/workflows/*.yml")) + \
                 glob.glob(str(proj_path / ".github/workflows/*.yaml")):
            try:
                content = Path(f).read_text(encoding="utf-8")
                if "opencode" in content.lower():
                    github_actions.setdefault(label, []).append(Path(f).stem)
            except OSError:
                pass

        # opencode.json / opencode.jsonc — parse for MCP, formatters, permissions, plugins, commands, agents
        for cfg_name in ["opencode.json", "opencode.jsonc"]:
            cfg_path = proj_path / cfg_name
            if not cfg_path.exists():
                continue
            try:
                import re as _re
                raw = cfg_path.read_text(encoding="utf-8")
                # Strip JSONC comments
                raw = _re.sub(r'//.*?$', '', raw, flags=_re.MULTILINE)
                raw = _re.sub(r'/\*.*?\*/', '', raw, flags=_re.DOTALL)
                cfg = json.loads(raw)
            except (json.JSONDecodeError, OSError):
                continue

            # MCP servers
            mcp = cfg.get("mcp", {})
            if mcp:
                mcp_servers.setdefault(label, []).extend(mcp.keys())

            # Formatters
            fmt = cfg.get("formatter", {})
            if fmt:
                formatters.setdefault(label, []).extend(fmt.keys())

            # Permissions
            perm = cfg.get("permission", {})
            if perm:
                permissions[label] = perm

            # Plugins from config
            plug = cfg.get("plugin", [])
            if plug:
                if isinstance(plug, list):
                    plugins.setdefault(label, []).extend(plug)
                elif isinstance(plug, dict):
                    plugins.setdefault(label, []).extend(plug.keys())

            # Commands from config
            cmds = cfg.get("command", {})
            if cmds:
                commands.setdefault(label, []).extend(cmds.keys())

            # Agents from config
            ags = cfg.get("agent", {})
            if ags:
                agents.setdefault(label, []).extend(ags.keys())

            # Key config values
            config_summary = {}
            if cfg.get("model"):
                config_summary["model"] = cfg["model"]
            if cfg.get("default_agent"):
                config_summary["default_agent"] = cfg["default_agent"]
            if cfg.get("compaction"):
                config_summary["compaction"] = cfg["compaction"]
            if cfg.get("share"):
                config_summary["share"] = cfg["share"]
            if config_summary:
                opencode_config[label] = config_summary

            break  # Only read first config found

        # AGENTS.md
        amd = proj_path / "AGENTS.md"
        if amd.exists():
            try:
                content = amd.read_text(encoding="utf-8")[:2000]
                agents_md[label] = content
            except OSError:
                pass

    # Deduplicate lists
    for d in [agents, skills, commands, tools, plugins, mcp_servers, formatters, github_actions]:
        for k in d:
            if isinstance(d[k], list):
                d[k] = sorted(set(d[k]))

    return {
        "agents": agents,
        "skills": skills,
        "commands": commands,
        "tools": tools,
        "agents_md": agents_md,
        "mcp_servers": mcp_servers,
        "plugins": plugins,
        "formatters": formatters,
        "permissions": permissions,
        "github_actions": github_actions,
        "opencode_config": opencode_config,
    }


def _is_warmup(session: dict, user_msg_count: int) -> bool:
    """Check if this is a warmup/minimal session."""
    if user_msg_count <= 1:
        return True
    title = (session.get("title") or "").lower()
    if "warmup" in title or "cache warm" in title:
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Extract OpenCode session data")
    parser.add_argument("--db", type=str, help="Path to opencode.db")
    parser.add_argument("--out", type=str, help="Output working directory (created if needed)")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    if db_path and not db_path.exists():
        print(
            f"ERROR: OpenCode database not found at {db_path} — "
            "is OpenCode installed and has it been used?",
            file=sys.stderr,
        )
        sys.exit(1)

    # Create working directory
    if args.out:
        work_dir = Path(args.out)
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="opencode-insights-"))

    transcripts_dir = work_dir / "transcripts"
    transcripts_dir.mkdir(exist_ok=True)

    conn = connect(db_path)
    try:
        sessions = fetch_sessions(conn)
        print(f"Found {len(sessions)} non-archived top-level sessions", file=sys.stderr)

        all_meta = []
        seen_ids = set()

        for session in sessions:
            sid = session["id"]

            # Deduplicate
            if sid in seen_ids:
                continue
            seen_ids.add(sid)

            # Duration filter
            start = session.get("time_created")
            end = session.get("time_updated")
            if start and end and (end - start) < 60000:
                continue

            messages = fetch_messages(conn, sid)
            msg_ids = [m["id"] for m in messages]
            parts_by_msg = fetch_parts_for_messages(conn, msg_ids)

            # Self-referential filter
            if _is_self_referential(parts_by_msg, messages):
                continue

            # Extract stats
            stats = extract_session_stats(session, messages, parts_by_msg)

            # User message count filter
            if stats["user_message_count"] < 2:
                continue

            # Warmup filter
            if _is_warmup(session, stats["user_message_count"]):
                continue

            # Roll up child session stats (subagent sessions)
            child_sessions = fetch_child_sessions(conn, sid)
            child_summaries = []  # For transcript enrichment
            for child in child_sessions:
                child_msgs = fetch_messages(conn, child["id"])
                child_msg_ids = [m["id"] for m in child_msgs]
                child_parts = fetch_parts_for_messages(conn, child_msg_ids)

                # Roll up quantitative stats
                child_rollup = extract_child_rollup(child_msgs, child_parts)
                merge_child_rollup(stats, child_rollup)

                # Extract child summary (last assistant text part)
                child_agent = ""
                for cm in child_msgs:
                    a = cm.get("data", {}).get("agent", "")
                    if a:
                        child_agent = a
                        break

                last_text = ""
                for cm in reversed(child_msgs):
                    if cm.get("data", {}).get("role") != "assistant":
                        continue
                    for p in child_parts.get(cm["id"], []):
                        pd = p.get("data", {})
                        if pd.get("type") == "text" and pd.get("text"):
                            last_text = pd["text"][:500]
                            break
                    if last_text:
                        break

                if child_agent and last_text:
                    child_summaries.append((child_agent, last_text))

            all_meta.append(stats)

            # Write transcript with child session summaries
            transcript = serialize_transcript(messages, parts_by_msg)
            if child_summaries:
                transcript += "\n\n--- SUBAGENT RESULTS ---\n"
                for agent_name, summary in child_summaries:
                    transcript += f"\n[SUBAGENT: {agent_name}]\n{summary}\n"
            (transcripts_dir / f"{sid}.txt").write_text(transcript, encoding="utf-8")

        # Write metadata
        meta_path = work_dir / "meta.json"
        meta_path.write_text(json.dumps(all_meta, indent=2), encoding="utf-8")

        # Discover existing user setup (agents, skills, commands, tools, AGENTS.md)
        user_setup = _discover_user_setup(all_meta)
        (work_dir / "user_setup.json").write_text(
            json.dumps(user_setup, indent=2), encoding="utf-8"
        )

        # Write config
        config = {
            "db_path": str(db_path or "auto"),
            "work_dir": str(work_dir),
            "total_sessions_found": len(sessions),
            "sessions_after_filter": len(all_meta),
        }
        (work_dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

        # Determine uncached sessions
        facets_cache = Path.home() / ".local" / "share" / "opencode" / "insights" / "facets"
        cached_ids = set()
        if facets_cache.exists():
            cached_ids = {f.stem for f in facets_cache.glob("*.json")}
        uncached = [m["session_id"] for m in all_meta if m["session_id"] not in cached_ids][:50]
        (work_dir / "uncached_sessions.json").write_text(json.dumps(uncached), encoding="utf-8")

        print(f"Extracted {len(all_meta)} qualifying sessions to {work_dir}", file=sys.stderr)
        # Print work dir path to stdout for the orchestrating agent
        print(str(work_dir))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
