"""
SQLite-backed message history for the notification server.

Every broadcast/direct message that passes through the server is saved
here so it can be replayed via GET /messages, independent of Redis or
any in-memory state.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import Any


class MessageStore:
    def __init__(self, database_url: str) -> None:
        self._path = database_url
        self._init_lock = asyncio.Lock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    async def init(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._init_sync)
            self._initialized = True

    def _init_sync(self) -> None:
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

    async def save(self, message: dict) -> int:
        await self.init()
        return await asyncio.to_thread(self._save_sync, message)

    def _save_sync(self, message: dict) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"]),
                    message["timestamp"],
                ),
            )
            conn.commit()
            return cursor.lastrowid

    async def list_messages(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        await self.init()
        return await asyncio.to_thread(self._list_sync, limit, offset)

    def _list_sync(self, limit: int, offset: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["payload"] = json.loads(item["payload"])
                results.append(item)
            return results

    async def list_by_channel(
        self, channel: str, since: str | None = None, limit: int = 50
    ) -> tuple[list[dict[str, Any]], bool]:
        """Chronological history for a channel, optionally since a timestamp.

        Fetches one extra row beyond `limit` to determine `has_more`
        without a second COUNT query.
        """
        await self.init()
        return await asyncio.to_thread(self._list_by_channel_sync, channel, since, limit)

    def _list_by_channel_sync(
        self, channel: str, since: str | None, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        with self._connect() as conn:
            query = "SELECT id, channel, type, payload, timestamp FROM messages WHERE channel = ?"
            params: list[Any] = [channel]
            if since:
                query += " AND timestamp > ?"
                params.append(since)
            query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
            params.append(limit + 1)
            rows = conn.execute(query, params).fetchall()
            has_more = len(rows) > limit
            results = []
            for row in rows[:limit]:
                item = dict(row)
                item["payload"] = json.loads(item["payload"])
                results.append(item)
            return results, has_more

    async def delete_older_than(self, cutoff_timestamp: str) -> int:
        """Delete messages with a timestamp before `cutoff_timestamp`. Returns rows deleted."""
        await self.init()
        return await asyncio.to_thread(self._delete_older_than_sync, cutoff_timestamp)

    def _delete_older_than_sync(self, cutoff_timestamp: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_timestamp,))
            conn.commit()
            return cursor.rowcount
