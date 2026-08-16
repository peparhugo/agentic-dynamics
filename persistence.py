"""
SQLite-backed message history for the notification server.

Every broadcast/direct message that passes through the server is recorded
here so it can be retrieved after the fact (e.g. a client that reconnects
after missing some traffic can page back through history via
GET /messages). Each call opens its own short-lived sqlite3 connection --
the same pattern used elsewhere in this codebase -- and every operation is
run through asyncio.to_thread so the blocking sqlite3 calls never stall the
event loop that drives the WebSocket server.
"""

from __future__ import annotations

import asyncio
import sqlite3
from typing import Optional


class MessageStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_sync(self) -> None:
        """Create the messages table if needed. Safe to call directly
        (blocking) at server startup before the event loop has other work
        competing for it -- the same synchronous-at-startup pattern used by
        this codebase's other seed apps for schema creation."""
        with self._connect() as conn:
            conn.execute(
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

    async def init_db(self) -> None:
        await asyncio.to_thread(self.init_sync)

    def _store_message_sync(
        self, channel: Optional[str], msg_type: str, payload: str, timestamp: str
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (channel, msg_type, payload, timestamp),
            )
            conn.commit()
            return cursor.lastrowid

    async def store_message(
        self, channel: Optional[str], msg_type: str, payload: str, timestamp: str
    ) -> int:
        return await asyncio.to_thread(
            self._store_message_sync, channel, msg_type, payload, timestamp
        )

    def _get_messages_sync(self, limit: int, offset: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    async def get_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        return await asyncio.to_thread(self._get_messages_sync, limit, offset)

    def _get_history_sync(
        self, channel: Optional[str], since: Optional[str], limit: int
    ) -> tuple[list[dict], bool]:
        conditions = []
        args: list = []
        if channel is not None:
            conditions.append("channel = ?")
            args.append(channel)
        if since is not None:
            conditions.append("timestamp > ?")
            args.append(since)
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        # Fetch one extra row to learn whether more history exists beyond
        # this page without a separate COUNT(*) query.
        args.append(limit + 1)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id, channel, type, payload, timestamp FROM messages "
                f"{where_clause} ORDER BY timestamp ASC, id ASC LIMIT ?",
                args,
            ).fetchall()
        has_more = len(rows) > limit
        return [dict(row) for row in rows[:limit]], has_more

    async def get_history(
        self, channel: Optional[str] = None, since: Optional[str] = None, limit: int = 50
    ) -> tuple[list[dict], bool]:
        return await asyncio.to_thread(self._get_history_sync, channel, since, limit)

    def _delete_older_than_sync(self, cutoff_timestamp: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff_timestamp,)
            )
            conn.commit()
            return cursor.rowcount

    async def delete_older_than(self, cutoff_timestamp: str) -> int:
        return await asyncio.to_thread(self._delete_older_than_sync, cutoff_timestamp)
