#!/usr/bin/env python3
"""Step 3: Merge session metadata + facets into aggregate JSON.

Usage:
    python3 aggregate.py --work /tmp/opencode-insights-XXXXX/
"""

import argparse
import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).parent))

from lib.schema import validate_facets
from lib.prompts import write_section_prompts
from lib.labels import FRICTION_TYPES, GOAL_CATEGORIES

ALLOWED_FRICTION_KEYS = set(FRICTION_TYPES.keys())
ALLOWED_GOAL_KEYS = set(GOAL_CATEGORIES.keys())

FACETS_CACHE_DIR = Path.home() / ".local" / "share" / "opencode" / "insights" / "facets"


def _merge_counters(target: dict, source: dict) -> None:
    """Merge a source counter dict into target in-place."""
    for k, v in source.items():
        target[k] = target.get(k, 0) + v


def _detect_parallel_sessions(all_meta: list[dict]) -> dict:
    """Detect parallel session usage via sliding 30-minute window."""
    # Collect all (timestamp, session_id) pairs
    all_stamps: list[tuple[int, str]] = []
    for meta in all_meta:
        sid = meta["session_id"]
        for ts in meta.get("user_message_timestamps", []):
            all_stamps.append((ts, sid))
    all_stamps.sort()

    overlap_pairs: set[tuple[str, str]] = set()
    sessions_involved: set[str] = set()
    user_messages_during = 0
    window_ms = 30 * 60 * 1000  # 30 minutes

    for i, (ts, sid) in enumerate(all_stamps):
        for j in range(i + 1, len(all_stamps)):
            ts2, sid2 = all_stamps[j]
            if ts2 - ts > window_ms:
                break
            if sid != sid2:
                pair = tuple(sorted([sid, sid2]))
                if pair not in overlap_pairs:
                    overlap_pairs.add(pair)
                    sessions_involved.add(sid)
                    sessions_involved.add(sid2)
                user_messages_during += 1

    return {
        "overlap_events": len(overlap_pairs),
        "sessions_involved": len(sessions_involved),
        "user_messages_during": user_messages_during,
    }


def main():
    parser = argparse.ArgumentParser(description="Aggregate session data + facets")
    parser.add_argument("--work", required=True, help="Working directory path")
    args = parser.parse_args()

    work = Path(args.work)
    meta_path = work / "meta.json"
    facets_dir = work / "facets"
    facets_dir.mkdir(exist_ok=True)

    all_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Copy cached facets into working dir
    FACETS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for cached in FACETS_CACHE_DIR.glob("*.json"):
        dest = facets_dir / cached.name
        if not dest.exists():
            shutil.copy2(cached, dest)

    # Load facets
    facets_map: dict[str, dict] = {}
    for f in facets_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if not validate_facets(data):
                f.unlink()  # Invalid cache, remove
                continue
            # Check for non-standard keys
            goal_keys = set(data.get("goal_categories", {}).keys())
            friction_keys = set(data.get("friction_counts", {}).keys())
            if goal_keys and not goal_keys.issubset(ALLOWED_GOAL_KEYS):
                f.unlink()  # Invalid cache
                continue
            if friction_keys and not friction_keys.issubset(ALLOWED_FRICTION_KEYS):
                f.unlink()
                continue
            sid = f.stem
            facets_map[sid] = data
        except (json.JSONDecodeError, OSError):
            pass

    # Aggregate
    total_sessions = len(all_meta)
    sessions_with_facets = 0
    total_messages = 0
    total_duration_hours = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    total_reasoning_tokens = 0
    total_cost = 0.0
    tool_counts: Counter = Counter()
    languages: Counter = Counter()
    git_commits = 0
    git_pushes = 0
    projects: Counter = Counter()
    goal_categories: Counter = Counter()
    outcomes: Counter = Counter()
    satisfaction: Counter = Counter()
    helpfulness: Counter = Counter()
    session_types: Counter = Counter()
    friction: Counter = Counter()
    success: Counter = Counter()
    total_tool_errors = 0
    tool_error_categories: Counter = Counter()
    all_response_times: list[float] = []
    total_lines_added = 0
    total_lines_removed = 0
    total_files_modified = 0
    all_message_hours: list[int] = []
    agent_counts: Counter = Counter()
    model_counts: Counter = Counter()
    child_agent_counts: Counter = Counter()
    child_model_counts: Counter = Counter()
    cost_by_model: Counter = Counter()
    session_summaries: list[dict] = []
    friction_details: list[str] = []
    sessions_using_task_agent = 0
    sessions_using_mcp = 0
    sessions_using_web_search = 0
    sessions_using_web_fetch = 0
    all_timestamps: list[str] = []

    for meta in all_meta:
        sid = meta["session_id"]
        total_messages += meta.get("user_message_count", 0) + meta.get("assistant_message_count", 0)
        total_duration_hours += meta.get("duration_minutes", 0) / 60.0
        total_input_tokens += meta.get("input_tokens", 0)
        total_output_tokens += meta.get("output_tokens", 0)
        total_reasoning_tokens += meta.get("reasoning_tokens", 0)
        total_cost += meta.get("cost", 0)
        _merge_counters(tool_counts, meta.get("tool_counts", {}))
        _merge_counters(languages, meta.get("languages", {}))
        git_commits += meta.get("git_commits", 0)
        git_pushes += meta.get("git_pushes", 0)
        proj = meta.get("project_path", "")
        if proj:
            projects[proj] += 1
        total_tool_errors += meta.get("tool_errors", 0)
        _merge_counters(tool_error_categories, meta.get("tool_error_categories", {}))
        all_response_times.extend(meta.get("user_response_times", []))
        total_lines_added += meta.get("lines_added", 0)
        total_lines_removed += meta.get("lines_removed", 0)
        total_files_modified += meta.get("files_modified", 0)
        all_message_hours.extend(meta.get("message_hours", []))
        _merge_counters(agent_counts, meta.get("agent_counts", {}))
        _merge_counters(model_counts, meta.get("model_counts", {}))
        _merge_counters(child_agent_counts, meta.get("child_agent_counts", {}))
        _merge_counters(child_model_counts, meta.get("child_model_counts", {}))

        # Cost by model
        for model_id, count in meta.get("model_counts", {}).items():
            if meta.get("cost", 0) and meta.get("assistant_message_count", 0):
                per_msg = meta["cost"] / meta["assistant_message_count"]
                cost_by_model[model_id] += round(per_msg * count, 4)

        if meta.get("uses_task_agent"):
            sessions_using_task_agent += 1
        if meta.get("uses_mcp"):
            sessions_using_mcp += 1
        if meta.get("uses_web_search"):
            sessions_using_web_search += 1
        if meta.get("uses_web_fetch"):
            sessions_using_web_fetch += 1

        start = meta.get("start_time", "")
        if start:
            all_timestamps.append(start)

        # Facet data
        facet = facets_map.get(sid)
        if facet:
            sessions_with_facets += 1
            _merge_counters(goal_categories, facet.get("goal_categories", {}))
            outcome = facet.get("outcome", "")
            if outcome:
                outcomes[outcome] += 1
            _merge_counters(satisfaction, facet.get("user_satisfaction_counts", {}))
            h = facet.get("assistant_helpfulness", "")
            if h:
                helpfulness[h] += 1
            st = facet.get("session_type", "")
            if st:
                session_types[st] += 1
            _merge_counters(friction, facet.get("friction_counts", {}))
            ps = facet.get("primary_success", "")
            if ps and ps != "none":
                success[ps] += 1
            fd = facet.get("friction_detail", "")
            if fd:
                friction_details.append(fd)

        # Session summary
        if len(session_summaries) < 50:
            session_summaries.append({
                "id": sid,
                "date": meta.get("start_time", ""),
                "summary": meta.get("summary", ""),
                "goal": facet.get("underlying_goal", "") if facet else "",
            })

    # Date range
    sorted_ts = sorted(all_timestamps) if all_timestamps else []
    date_range = {
        "start": sorted_ts[0] if sorted_ts else "",
        "end": sorted_ts[-1] if sorted_ts else "",
    }

    # Days active
    unique_days: set[str] = set()
    for ts in all_timestamps:
        unique_days.add(ts[:10])
    days_active = len(unique_days)
    messages_per_day = round(total_messages / max(days_active, 1), 1)

    # Response time stats
    median_rt = round(median(all_response_times), 1) if all_response_times else 0
    avg_rt = round(mean(all_response_times), 1) if all_response_times else 0

    # Parallel sessions
    parallel = _detect_parallel_sessions(all_meta)

    total_duration_hours = round(total_duration_hours, 1)

    aggregate = {
        "total_sessions": total_sessions,
        "sessions_with_facets": sessions_with_facets,
        "date_range": date_range,
        "total_messages": total_messages,
        "total_duration_hours": total_duration_hours,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "tool_counts": dict(tool_counts.most_common()),
        "languages": dict(Counter(languages).most_common()),
        "git_commits": git_commits,
        "git_pushes": git_pushes,
        "projects": dict(Counter(projects).most_common()),
        "goal_categories": dict(Counter(goal_categories).most_common()),
        "outcomes": dict(outcomes),
        "satisfaction": dict(satisfaction),
        "helpfulness": dict(helpfulness),
        "session_types": dict(Counter(session_types).most_common()),
        "friction": dict(Counter(friction).most_common()),
        "success": dict(Counter(success).most_common()),
        "session_summaries": session_summaries,
        "friction_details": friction_details,
        "total_tool_errors": total_tool_errors,
        "tool_error_categories": dict(Counter(tool_error_categories).most_common()),
        "user_response_times": all_response_times,
        "median_response_time": median_rt,
        "avg_response_time": avg_rt,
        "total_lines_added": total_lines_added,
        "total_lines_removed": total_lines_removed,
        "total_files_modified": total_files_modified,
        "days_active": days_active,
        "messages_per_day": messages_per_day,
        "message_hours": all_message_hours,
        "parallel_sessions": parallel,
        "total_reasoning_tokens": total_reasoning_tokens,
        "total_cost": round(total_cost, 2),
        "agent_counts": dict(Counter(agent_counts).most_common()),
        "model_counts": dict(Counter(model_counts).most_common()),
        "child_agent_counts": dict(Counter(child_agent_counts).most_common()),
        "child_model_counts": dict(Counter(child_model_counts).most_common()),
        "cost_by_model": {k: round(v, 2) for k, v in cost_by_model.most_common()},
        "sessions_using_task_agent": sessions_using_task_agent,
        "sessions_using_mcp": sessions_using_mcp,
        "sessions_using_web_search": sessions_using_web_search,
        "sessions_using_web_fetch": sessions_using_web_fetch,
    }

    # Write aggregate
    agg_path = work / "aggregate.json"
    agg_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    # Write context string
    from lib.prompts import build_section_context
    context = build_section_context(aggregate)
    (work / "context.txt").write_text(context, encoding="utf-8")

    # Load user setup if available
    user_setup = None
    user_setup_path = work / "user_setup.json"
    if user_setup_path.exists():
        user_setup = json.loads(user_setup_path.read_text(encoding="utf-8"))

    # Write section prompts
    prompts_dir = work / "prompts"
    write_section_prompts(str(prompts_dir), aggregate, user_setup)

    # Identify uncached sessions
    uncached = [
        m["session_id"] for m in all_meta
        if m["session_id"] not in facets_map
    ][:50]
    uncached_path = work / "uncached_sessions.json"
    uncached_path.write_text(json.dumps(uncached), encoding="utf-8")

    # Copy new facets back to persistent cache
    for f in facets_dir.glob("*.json"):
        dest = FACETS_CACHE_DIR / f.name
        if not dest.exists():
            shutil.copy2(f, dest)

    print(
        f"Aggregated {total_sessions} sessions "
        f"({sessions_with_facets} with facets, {len(uncached)} uncached)",
        file=sys.stderr,
    )
    print(str(work))


if __name__ == "__main__":
    main()
