"""
SQLite message history store.

Persists every application message (broadcast and direct) so history can be
queried via ``GET /messages``.

Schema
------
``messages`` table::

    id         INTEGER PRIMARY KEY AUTOINCREMENT
    channel    TEXT      -- channel name (NULL for global broadcasts/directs)
    type       TEXT      -- "broadcast" or "direct"
    payload    TEXT      -- JSON-encoded message payload
    timestamp  TEXT      -- ISO-8601 timestamp
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

DEFAULT_DATABASE_URL = "messages.db"


class MessageStore:
    """Thread-safe-enough SQLite store for message history."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_url)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )

    def save(self, message: Dict[str, Any]) -> int:
        channel = message.get("channel")
        mtype = message.get("type", "")
        payload = json.dumps(message.get("payload") or {})
        timestamp = message.get("timestamp") or ""
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, mtype, payload, timestamp),
            )
            conn.commit()
            return cursor.lastrowid

    def _row_to_message(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }

    def query(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 50
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0
        limit = max(0, min(limit, 1000))
        offset = max(0, offset)

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

        return [self._row_to_message(row) for row in rows]

    def query_history(
        self,
        channel: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Return messages for a channel/time range in chronological order.

        Results are ordered oldest-first (ascending ``id``).  ``since`` filters
        messages whose ``timestamp`` is greater than or equal to the given
        ISO-8601 value.  ``has_more`` is ``True`` when additional messages
        exist beyond the returned page.
        """
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 1000))

        conditions: List[str] = []
        params: List[Any] = []
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM messages{where} ORDER BY id ASC LIMIT ?",
                (*params, limit + 1),
            ).fetchall()

        has_more = len(rows) > limit
        messages = [self._row_to_message(row) for row in rows[:limit]]
        return {"messages": messages, "has_more": has_more}

    def delete_older_than_days(self, days: int) -> int:
        """Delete messages older than ``days`` and return the number removed."""
        try:
            days = int(days)
        except (TypeError, ValueError):
            days = 7
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE timestamp < ?",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
            return int(row["n"])
