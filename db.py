"""
SQLite persistence layer — sessions and messages.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DB_PATH = "chat.db"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT 'New Chat',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL DEFAULT '',
                tool_calls  TEXT,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
        """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(title: str = "New Chat") -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    now = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (sid, title, now, now),
        )
    return {"id": sid, "title": title, "created_at": now, "updated_at": now}


def list_sessions() -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_session(sid: str) -> Optional[Dict[str, Any]]:
    with _conn() as con:
        row = con.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
    return dict(row) if row else None


def update_session_title(sid: str, title: str) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, _now(), sid),
        )


def touch_session(sid: str) -> None:
    with _conn() as con:
        con.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), sid))


def delete_session(sid: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM sessions WHERE id = ?", (sid,))


# ── Messages ──────────────────────────────────────────────────────────────────

def add_message(
    session_id: str,
    role: str,
    content: str,
    tool_calls: Optional[Any] = None,
) -> Dict[str, Any]:
    mid = str(uuid.uuid4())
    now = _now()
    tc_json = json.dumps(tool_calls, default=str) if tool_calls is not None else None
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (id, session_id, role, content, tool_calls, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (mid, session_id, role, content, tc_json, now),
        )
    touch_session(session_id)
    return {
        "id": mid,
        "session_id": session_id,
        "role": role,
        "content": content,
        "tool_calls": tool_calls,
        "created_at": now,
    }


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if d["tool_calls"]:
            try:
                d["tool_calls"] = json.loads(d["tool_calls"])
            except Exception:
                d["tool_calls"] = []
        result.append(d)
    return result


def get_agent_history(session_id: str) -> List[Dict[str, str]]:
    """Lightweight text-only history for the agent context."""
    msgs = get_messages(session_id)
    return [
        {"role": m["role"], "content": m["content"]}
        for m in msgs
        if m["role"] in ("user", "assistant")
    ]
