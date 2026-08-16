"""SQLite-backed message history store.

All messages distributed by the server are persisted here so they can be
queried later via ``GET /messages``. The database location is configured
through the ``DATABASE_URL`` environment variable (``sqlite:///path``).
"""

import json
import logging
import os
import sqlite3

import aiosqlite

log = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///notifications.db")

_CREATE_MESSAGES_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL
)
"""

_SELECT_COLUMNS = "id, channel, type, payload, timestamp"


def sqlite_path(database_url: str) -> str:
    """Extract the filesystem path from a ``sqlite://`` URL."""
    if database_url.startswith("sqlite://"):
        database_url = database_url[len("sqlite://"):]
    if database_url in (":memory:", "/:memory:"):
        return ":memory:"
    return database_url


class MessageStore:
    """Async wrapper around a SQLite messages table."""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or DEFAULT_DATABASE_URL
        self._conn: aiosqlite.Connection | None = None

    # ── lifecycle ─────────────────────────────────────────────

    async def start(self) -> "MessageStore":
        """Open the database connection and ensure the schema exists."""
        path = sqlite_path(self.database_url)
        self._conn = await aiosqlite.connect(path)
        self._conn.row_factory = sqlite3.Row
        await self._conn.execute(_CREATE_MESSAGES_SQL)
        await self._conn.commit()
        return self

    async def stop(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    # ── queries ───────────────────────────────────────────────

    async def store(
        self,
        channel: str,
        message_type: str,
        payload: dict,
        timestamp: str,
    ) -> int:
        """Persist a message and return its assigned row id."""
        if self._conn is None:
            return -1
        cursor = await self._conn.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (channel, message_type, json.dumps(payload), timestamp),
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def list(self, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        """Return (messages, total) for the given pagination window."""
        if self._conn is None:
            return [], 0
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        cursor = await self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM messages "
            "ORDER BY id ASC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        count_cursor = await self._conn.execute("SELECT COUNT(*) AS n FROM messages")
        total = (await count_cursor.fetchone())[0]
        messages = []
        for row in rows:
            messages.append({
                "id": row["id"],
                "channel": row["channel"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            })
        return messages, total

    async def count(self) -> int:
        """Return the total number of stored messages."""
        if self._conn is None:
            return 0
        cursor = await self._conn.execute("SELECT COUNT(*) AS n FROM messages")
        return (await cursor.fetchone())[0]
