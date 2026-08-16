"""SQLite-backed message history store.

All messages distributed by the server are persisted here so they can be
queried later via ``GET /messages``. The database location is configured
through the ``DATABASE_URL`` environment variable (``sqlite:///path``).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

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


def _parse_iso(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp to a tz-aware datetime (or None)."""
    if isinstance(value, str):
        value = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


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

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert a database row to the public message dict shape."""
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }

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
        messages = [self._row_to_dict(row) for row in rows]
        return messages, total

    async def history(
        self,
        channel: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        """Return (messages, has_more) for a channel/time range, oldest first.

        ``channel`` filters on the channel column (omitted when None); ``since``
        filters to messages with a timestamp at or after the given ISO-8601
        timestamp. Messages are returned in chronological order and ``has_more``
        reports whether more matching messages exist beyond the returned page.
        """
        if self._conn is None:
            return [], False
        limit = max(1, int(limit))
        since_dt = _parse_iso(since) if since else None

        conditions, params = [], []
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)
        cursor = await self._conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM messages "
            f"{where} ORDER BY timestamp ASC, id ASC",
            params,
        )
        rows = await cursor.fetchall()
        messages = []
        for row in rows:
            message = self._row_to_dict(row)
            if since_dt is not None:
                message_dt = _parse_iso(message["timestamp"])
                if message_dt is None or message_dt < since_dt:
                    continue
            messages.append(message)
        has_more = len(messages) > limit
        return messages[:limit], has_more

    async def cleanup_expired(self, ttl_days: int) -> int:
        """Delete messages older than ``ttl_days`` days; return rows deleted."""
        if self._conn is None:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(0, int(ttl_days))
        )
        cursor = await self._conn.execute("SELECT id, timestamp FROM messages")
        rows = await cursor.fetchall()
        to_delete = [
            row["id"]
            for row in rows
            if _parse_iso(row["timestamp"]) is not None
            and _parse_iso(row["timestamp"]) < cutoff
        ]
        if not to_delete:
            return 0
        placeholders = ",".join("?" * len(to_delete))
        cursor = await self._conn.execute(
            f"DELETE FROM messages WHERE id IN ({placeholders})", to_delete
        )
        await self._conn.commit()
        return cursor.rowcount

    async def count(self) -> int:
        """Return the total number of stored messages."""
        if self._conn is None:
            return 0
        cursor = await self._conn.execute("SELECT COUNT(*) AS n FROM messages")
        return (await cursor.fetchone())[0]
