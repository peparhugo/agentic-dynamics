"""SQLite-backed persistence of routed messages, for history/replay."""

from __future__ import annotations

import asyncio
import json
import sqlite3


class MessageStore:
    """Persists broadcast/direct messages and serves them back for history.

    Every operation opens a short-lived sqlite3 connection on a worker
    thread via asyncio.to_thread, so the store is safe to share across
    concurrent asyncio tasks without holding a single connection (which
    sqlite3 does not allow across threads by default).
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )
            conn.commit()
        finally:
            conn.close()

    async def save(self, channel: str | None, msg_type: str, payload: dict, timestamp: str) -> int:
        return await asyncio.to_thread(self._save_sync, channel, msg_type, payload, timestamp)

    def _save_sync(self, channel: str | None, msg_type: str, payload: dict, timestamp: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), timestamp),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    async def list_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        return await asyncio.to_thread(self._list_sync, limit, offset)

    def _list_sync(self, limit: int, offset: int) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            messages = []
            for row in rows:
                message = dict(row)
                message["payload"] = json.loads(message["payload"])
                messages.append(message)
            return messages
        finally:
            conn.close()
