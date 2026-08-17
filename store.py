"""SQLite persistence for notification message history."""

import json
import sqlite3
import threading
from typing import Optional


def normalize_db_url(db_url: Optional[str]) -> str:
    """Convert a DATABASE_URL-style value to a SQLite path."""
    if not db_url:
        return ":memory:"
    for prefix in ("sqlite:///", "sqlite://"):
        if db_url.startswith(prefix):
            db_url = db_url[len(prefix):]
            break
    if not db_url:
        return ":memory:"
    return db_url


class MessageStore:
    """Thread-safe SQLite store for messages.

    Table schema: id, channel, type, payload, timestamp.
    """

    def __init__(self, db_url: Optional[str] = None) -> None:
        self._path = normalize_db_url(db_url)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                type TEXT,
                payload TEXT,
                timestamp TEXT
            )
            """
        )
        self._conn.commit()

    def save(self, message: dict) -> int:
        """Persist a message and return its assigned row id."""
        channel = message.get("channel")
        if channel is None:
            payload = message.get("payload")
            if isinstance(payload, dict):
                channel = payload.get("channel")
        payload_json = json.dumps(message.get("payload"))
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, message.get("type"), payload_json, message.get("timestamp")),
            )
            self._conn.commit()
            return cursor.lastrowid

    def query(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """Return messages ordered by most recent first, with pagination."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [self._row_to_message(row) for row in rows]

    def query_history(
        self, channel: str, since: Optional[str] = None, limit: int = 50
    ) -> dict:
        """Return messages for a channel in chronological order, paginated.

        Returns ``{"messages": [...], "has_more": bool}``. When ``since`` is
        provided, only messages with a timestamp >= ``since`` are included.
        """
        with self._lock:
            if since is None:
                rows = self._conn.execute(
                    """
                    SELECT id, channel, type, payload, timestamp
                    FROM messages
                    WHERE channel = ?
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (channel, limit + 1),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    """
                    SELECT id, channel, type, payload, timestamp
                    FROM messages
                    WHERE channel = ? AND timestamp >= ?
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (channel, since, limit + 1),
                ).fetchall()
        has_more = len(rows) > limit
        messages = [self._row_to_message(row) for row in rows[:limit]]
        return {"messages": messages, "has_more": has_more}

    def delete_older_than(self, cutoff: str) -> int:
        """Delete messages whose timestamp is strictly older than ``cutoff``."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM messages WHERE timestamp < ?", (cutoff,)
            )
            self._conn.commit()
            return cursor.rowcount

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    @staticmethod
    def _row_to_message(row) -> dict:
        return {
            "id": row[0],
            "channel": row[1],
            "type": row[2],
            "payload": json.loads(row[3]),
            "timestamp": row[4],
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
