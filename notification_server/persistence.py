"""SQLite-backed message history store.

Every message that flows through the notification server is written here so
it can be replayed later via the `GET /messages` REST endpoint, independent
of which Redis subscribers happened to be online when it was delivered.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from .messages import Message


class MessageStore:
    """Thread-safe wrapper around a single SQLite connection.

    A single persistent connection (guarded by a lock) is used rather than
    opening/closing per call, since messages can arrive rapidly from the
    Redis delivery worker.
    """

    def __init__(self, path: str = "notifications.db") -> None:
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def save(self, message: Message) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (
                    message.channel,
                    message.type,
                    json.dumps(message.payload),
                    message.timestamp,
                ),
            )
            self._conn.commit()
            return cursor.lastrowid

    def fetch(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "channel": row["channel"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
