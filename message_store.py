"""
SQLite persistence for notification message history.

Every relayed message (broadcasts, channel messages and direct messages) is
stored in a ``messages`` table so history survives restarts and can be
queried through the REST endpoint ``GET /messages?limit=50&offset=0``.

Table schema:
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    channel     TEXT NOT NULL DEFAULT ''
    type        TEXT NOT NULL
    payload     TEXT NOT NULL         (JSON-encoded)
    timestamp   TEXT NOT NULL

The database location comes from the ``DATABASE_URL`` environment variable,
either as a plain filesystem path or as a ``sqlite:///...`` URL.
"""

from __future__ import annotations

import json

import aiosqlite


def resolve_db_path(database_url: str) -> str:
    """Turn a DATABASE_URL value into a filesystem path sqlite can use."""
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    if database_url == "sqlite://":
        return ":memory:"
    return database_url


class MessageStore:
    """Async SQLite store for notification message history."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._db_path = resolve_db_path(database_url)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> "MessageStore":
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute(
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
        await self._conn.commit()
        return self

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def record(
        self,
        channel: str,
        msg_type: str,
        payload: dict,
        timestamp: str,
    ) -> None:
        await self._conn.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (channel, msg_type, json.dumps(payload), timestamp),
        )
        await self._conn.commit()

    async def count(self) -> int:
        cur = await self._conn.execute("SELECT COUNT(*) AS c FROM messages")
        row = await cur.fetchone()
        await cur.close()
        return int(row["c"])

    async def list_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return messages newest-first with pagination."""
        cur = await self._conn.execute(
            """
            SELECT id, channel, type, payload, timestamp
            FROM messages
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        )
        rows = await cur.fetchall()
        await cur.close()
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
