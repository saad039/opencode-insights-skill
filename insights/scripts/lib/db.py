"""SQLite database access for OpenCode session data."""

import json
import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def get_db_path() -> Path:
    """Return the OpenCode database path, raising if not found."""
    p = DEFAULT_DB_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"OpenCode database not found at {p} — "
            "is OpenCode installed and has it been used?"
        )
    return p


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a read-only connection to the OpenCode database."""
    p = db_path or get_db_path()
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_sessions(conn: sqlite3.Connection) -> list[dict]:
    """Fetch all non-archived top-level sessions ordered by time_created DESC."""
    rows = conn.execute(
        """
        SELECT id, project_id, parent_id, slug, directory, title, version,
               summary_additions, summary_deletions, summary_files,
               time_created, time_updated, time_archived
        FROM session
        WHERE time_archived IS NULL
          AND parent_id IS NULL
        ORDER BY time_created DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_messages(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    """Fetch all messages for a session, ordered by time_created."""
    rows = conn.execute(
        """
        SELECT id, session_id, time_created, time_updated, data
        FROM message
        WHERE session_id = ?
        ORDER BY time_created ASC
        """,
        (session_id,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d["data"]) if d["data"] else {}
        results.append(d)
    return results


def fetch_parts(conn: sqlite3.Connection, session_id: str) -> list[dict]:
    """Fetch all parts for a session, ordered by time_created."""
    rows = conn.execute(
        """
        SELECT id, message_id, session_id, time_created, time_updated, data
        FROM part
        WHERE session_id = ?
        ORDER BY time_created ASC
        """,
        (session_id,),
    ).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d["data"]) if d["data"] else {}
        results.append(d)
    return results


def fetch_child_sessions(conn: sqlite3.Connection, parent_id: str) -> list[dict]:
    """Fetch all child sessions for a parent session."""
    rows = conn.execute(
        """
        SELECT id, project_id, parent_id, slug, directory, title, version,
               summary_additions, summary_deletions, summary_files,
               time_created, time_updated, time_archived
        FROM session
        WHERE parent_id = ?
        ORDER BY time_created ASC
        """,
        (parent_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_parts_for_messages(
    conn: sqlite3.Connection, message_ids: list[str]
) -> dict[str, list[dict]]:
    """Fetch parts grouped by message_id for a list of message IDs."""
    if not message_ids:
        return {}
    placeholders = ",".join("?" for _ in message_ids)
    rows = conn.execute(
        f"""
        SELECT id, message_id, session_id, time_created, time_updated, data
        FROM part
        WHERE message_id IN ({placeholders})
        ORDER BY time_created ASC
        """,
        message_ids,
    ).fetchall()
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d["data"]) if d["data"] else {}
        grouped.setdefault(d["message_id"], []).append(d)
    return grouped
