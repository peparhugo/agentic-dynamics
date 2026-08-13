"""SQLite-backed persistence for message history.

Every broadcast and direct message that the notification server routes is
recorded here so it can be replayed via `GET /messages`. Storage is plain
`sqlite3`; the `arecord`/`alist_messages` wrappers run the blocking calls in
a thread so they don't stall the asyncio event loop.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import Any


class MessageStore:
    def __init__(self, path: str = "notifications.db") -> None:
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
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

    def record(
        self, msg_type: str, payload: dict[str, Any], timestamp: str, channel: str | None = None
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), timestamp),
            )
            conn.commit()
            return cursor.lastrowid

    def list_messages(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
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

    async def arecord(
        self, msg_type: str, payload: dict[str, Any], timestamp: str, channel: str | None = None
    ) -> int:
        return await asyncio.to_thread(self.record, msg_type, payload, timestamp, channel)

    async def alist_messages(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.list_messages, limit, offset)
