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
        return [self._row_to_message(row) for row in rows]

    def list_history(
        self, channel: str | None = None, since: str | None = None, limit: int = 50
    ) -> tuple[list[dict[str, Any]], bool]:
        """Chronological messages for a channel/time range, with pagination.

        Returns `(messages, has_more)`. `since` (when given) selects messages
        strictly after that ISO timestamp, so a client can pass the
        timestamp of the last message it saw to fetch only what's new.
        """
        query = "SELECT id, channel, type, payload, timestamp FROM messages WHERE 1=1"
        params: list[Any] = []
        if channel is not None:
            query += " AND channel = ?"
            params.append(channel)
        if since is not None:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        params.append(limit + 1)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        has_more = len(rows) > limit
        messages = [self._row_to_message(row) for row in rows[:limit]]
        return messages, has_more

    def delete_older_than(self, cutoff_timestamp: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff_timestamp,)
            )
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }

    async def arecord(
        self, msg_type: str, payload: dict[str, Any], timestamp: str, channel: str | None = None
    ) -> int:
        return await asyncio.to_thread(self.record, msg_type, payload, timestamp, channel)

    async def alist_messages(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self.list_messages, limit, offset)

    async def alist_history(
        self, channel: str | None = None, since: str | None = None, limit: int = 50
    ) -> tuple[list[dict[str, Any]], bool]:
        return await asyncio.to_thread(self.list_history, channel, since, limit)

    async def adelete_older_than(self, cutoff_timestamp: str) -> int:
        return await asyncio.to_thread(self.delete_older_than, cutoff_timestamp)
