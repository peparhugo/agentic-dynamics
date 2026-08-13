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
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

DEFAULT_DATABASE_URL = os.environ.get("DATABASE_URL", "notification.db")


def normalize_timestamp(timestamp: str) -> str:
    """Normalize an ISO-8601 timestamp to a canonical, lexically sortable form.

    All stored timestamps are converted to UTC ISO-8601 with a fixed width so
    that string comparison in SQLite matches chronological order.
    """
    ts = timestamp
    if ts.endswith(("Z", "z")):
        ts = ts[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return timestamp
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


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
        normalized = normalize_timestamp(timestamp)
        cursor = self._conn.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (channel, msg_type, json.dumps(payload), normalized),
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

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a messages row into a JSON-friendly dict."""
        record = dict(row)
        record["payload"] = json.loads(record["payload"])
        return record

    def history(
        self,
        channel: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return stored messages in chronological order for a channel/range.

        ``channel`` filters to a single channel (use ``""`` for broadcasts);
        ``None`` returns messages from every channel. ``since`` is an ISO-8601
        timestamp; only messages strictly newer than it are returned. Messages
        are ordered oldest-first and pagination is cursor-based on ``since``:
        up to ``limit`` messages are returned along with a ``has_more`` flag
        indicating whether additional older/newer messages exist.
        """
        limit = max(1, min(int(limit), 1000))
        conditions: list[str] = []
        params: list[Any] = []
        if channel is not None:
            conditions.append("channel = ?")
            params.append(channel)
        if since:
            conditions.append("timestamp > ?")
            params.append(normalize_timestamp(since))
        sql = "SELECT id, channel, type, payload, timestamp FROM messages"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        rows = self._conn.execute(sql, params + [limit + 1]).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        return [self._decode_row(row) for row in rows], has_more

    def delete_older_than(self, days: float) -> int:
        """Delete messages older than ``days`` days and return the count."""
        days = max(0, float(days))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            "DELETE FROM messages WHERE timestamp < ?", (normalize_timestamp(cutoff),)
        )
        self._conn.commit()
        return cursor.rowcount
