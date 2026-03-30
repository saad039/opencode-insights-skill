#!/usr/bin/env python3
"""Build compact context for the orchestrating agent to answer follow-up questions.

Usage:
    python3 build_return_context.py --work /tmp/opencode-insights-XXXXX/
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.prompts import build_section_context


def main():
    parser = argparse.ArgumentParser(description="Build return context")
    parser.add_argument("--work", required=True, help="Working directory")
    args = parser.parse_args()

    work = Path(args.work)
    aggregate = json.loads((work / "aggregate.json").read_text(encoding="utf-8"))

    sections_dir = work / "sections"
    sections = {}
    for f in sections_dir.glob("*.json"):
        try:
            sections[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # Build compact context
    lines = []
    lines.append("=== OPENCODE INSIGHTS DATA ===\n")
    lines.append(build_section_context(aggregate))
    lines.append("\n\n=== SECTION RESULTS ===\n")
    for name, data in sections.items():
        lines.append(f"\n## {name}\n{json.dumps(data, indent=2)}")

    # Find report path
    report_path = Path.home() / ".local" / "share" / "opencode" / "insights" / "report.html"
    lines.append(f"\n\n=== REPORT ===\nfile://{report_path}")

    context = "\n".join(lines)
    out_path = work / "return_context.txt"
    out_path.write_text(context, encoding="utf-8")

    print(f"Return context written to {out_path}", file=sys.stderr)
    print(str(out_path))


if __name__ == "__main__":
    main()
