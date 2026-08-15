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

        messages: List[Dict[str, Any]] = []
        for row in rows:
            messages.append(
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                }
            )
        return messages

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
            return int(row["n"])
