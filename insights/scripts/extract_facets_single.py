#!/usr/bin/env python3
"""Helper for facet extraction subagents.

Usage:
    # Read and chunk a transcript:
    python3 extract_facets_single.py read --transcript /path/to/session.txt

    # Validate and write a facet result:
    python3 extract_facets_single.py write --facet /path/to/output.json --data '{"underlying_goal":...}'
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.transcript import chunk_transcript
from lib.prompts import FACET_EXTRACTION_PROMPT, FACET_RESPONSE_SCHEMA, CHUNK_SUMMARY_PROMPT
from lib.schema import validate_facets


def cmd_read(args):
    """Read a transcript and output it with the facet extraction prompt."""
    transcript = Path(args.transcript).read_text(encoding="utf-8")
    chunks = chunk_transcript(transcript, max_chars=30000)

    if len(chunks) > 1:
        # Multiple chunks need summarization first
        print(json.dumps({
            "needs_chunking": True,
            "num_chunks": len(chunks),
            "chunks": chunks,
            "chunk_summary_prompt": CHUNK_SUMMARY_PROMPT,
            "facet_prompt": FACET_EXTRACTION_PROMPT,
            "facet_schema": FACET_RESPONSE_SCHEMA,
        }))
    else:
        # Single chunk — output the full prompt
        print(json.dumps({
            "needs_chunking": False,
            "prompt": FACET_EXTRACTION_PROMPT + transcript + FACET_RESPONSE_SCHEMA,
        }))


def cmd_write(args):
    """Validate and write a facet JSON result."""
    try:
        data = json.loads(args.data)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not validate_facets(data):
        print("ERROR: Facet data missing required fields", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.facet)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Facet written to {out_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Facet extraction helper")
    sub = parser.add_subparsers(dest="command")

    read_p = sub.add_parser("read", help="Read and prepare transcript")
    read_p.add_argument("--transcript", required=True)

    write_p = sub.add_parser("write", help="Validate and write facet")
    write_p.add_argument("--facet", required=True)
    write_p.add_argument("--data", required=True)

    args = parser.parse_args()
    if args.command == "read":
        cmd_read(args)
    elif args.command == "write":
        cmd_write(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
