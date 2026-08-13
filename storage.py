"""SQLite persistence for notification message history.

Every routed message is stored in a ``messages`` table:

    CREATE TABLE messages (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        channel    TEXT NOT NULL DEFAULT '',
        type       TEXT NOT NULL,
        payload    TEXT NOT NULL,        -- JSON-encoded dict
        timestamp  TEXT NOT NULL
    );

The database path is configured through the ``DATABASE_URL`` environment
variable. Messages are read back through the REST endpoint
``GET /messages?limit=50&offset=0``.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any, Optional

DEFAULT_DATABASE_URL = os.environ.get("DATABASE_URL", "notification.db")


class MessageStore:
    """Thread-safe (single connection) SQLite store for message history."""

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = (
            database_url or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
        )
        self._conn = sqlite3.connect(self.database_url, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def add(
        self,
        channel: str,
        msg_type: str,
        payload: dict,
        timestamp: str,
    ) -> int:
        """Persist a message and return its row id."""
        cursor = self._conn.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (channel, msg_type, json.dumps(payload), timestamp),
        )
        self._conn.commit()
        return cursor.lastrowid

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """Return stored messages, newest first, honoring limit/offset."""
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        rows = self._conn.execute(
            "SELECT id, channel, type, payload, timestamp "
            "FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        messages: list[dict[str, Any]] = []
        for row in rows:
            record = dict(row)
            record["payload"] = json.loads(record["payload"])
            messages.append(record)
        return messages

    def count(self) -> int:
        """Return the total number of stored messages."""
        row = self._conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
        return int(row["n"])
