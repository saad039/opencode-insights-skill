#!/usr/bin/env python3
"""Render the final HTML report from aggregate + section data.

Usage:
    python3 render_html.py --work /tmp/opencode-insights-XXXXX/ --out ~/.local/share/opencode/insights/report.html
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.html_template import render_html_report


def _repair_json(text: str) -> str:
    """Attempt to repair common LLM JSON errors.

    LLMs sometimes produce JSON with invalid escape sequences like \\---
    or unescaped newlines in strings. This function fixes those before parsing.
    """
    # Fix invalid escape sequences: replace \X (where X is not a valid JSON escape)
    # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    def fix_escapes(m):
        char = m.group(1)
        if char in ('"', '\\', '/', 'b', 'f', 'n', 'r', 't'):
            return m.group(0)  # valid escape, keep it
        if char == 'u':
            return m.group(0)  # unicode escape, keep it
        return char  # invalid escape, drop the backslash

    return re.sub(r'\\(.)', fix_escapes, text)


def _load_json_file(path: Path) -> dict | None:
    """Load a JSON file with repair fallback for LLM-generated content."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"Warning: Could not read {path.name}: {e}", file=sys.stderr)
        return None

    # Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try repairing invalid escapes
    try:
        repaired = _repair_json(text)
        result = json.loads(repaired)
        print(f"Repaired invalid JSON in {path.name}", file=sys.stderr)
        return result
    except json.JSONDecodeError as e:
        print(f"Warning: Could not parse {path.name} even after repair: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Render OpenCode Insights HTML report")
    parser.add_argument("--work", required=True, help="Working directory")
    parser.add_argument("--out", required=True, help="Output HTML file path")
    args = parser.parse_args()

    work = Path(args.work)
    aggregate = json.loads((work / "aggregate.json").read_text(encoding="utf-8"))

    sections_dir = work / "sections"
    sections = {}
    for f in sections_dir.glob("*.json"):
        data = _load_json_file(f)
        if data is not None:
            sections[f.stem] = data

    html = render_html_report(aggregate, sections)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    print(f"Report written to {out_path}", file=sys.stderr)
    print(str(out_path))


if __name__ == "__main__":
    main()
