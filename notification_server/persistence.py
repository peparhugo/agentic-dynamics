"""SQLite-backed message history store.

Every message that flows through the notification server is written here so
it can be replayed later via the `GET /messages` REST endpoint, independent
of which Redis subscribers happened to be online when it was delivered.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from .messages import Message


class MessageStore:
    """Thread-safe wrapper around a single SQLite connection.

    A single persistent connection (guarded by a lock) is used rather than
    opening/closing per call, since messages can arrive rapidly from the
    Redis delivery worker.
    """

    def __init__(self, path: str = "notifications.db") -> None:
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
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
            self._conn.commit()

    def save(self, message: Message) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (
                    message.channel,
                    message.type,
                    json.dumps(message.payload),
                    message.timestamp,
                ),
            )
            self._conn.commit()
            return cursor.lastrowid

    def fetch(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def history(
        self, channel: str | None = None, since: str | None = None, limit: int = 50
    ) -> dict[str, Any]:
        """Chronological (oldest-first) message history, optionally filtered
        to a `channel` and/or messages timestamped at or after `since` (an
        ISO-8601 string). Fetches one extra row to derive `has_more` without
        a separate COUNT query."""
        clauses = []
        params: list[Any] = []
        if channel is not None:
            clauses.append("channel = ?")
            params.append(channel)
        if since is not None:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit + 1)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT id, channel, type, payload, timestamp FROM messages "
                f"{where} ORDER BY id ASC LIMIT ?",
                params,
            ).fetchall()
        has_more = len(rows) > limit
        return {
            "messages": [self._row_to_dict(row) for row in rows[:limit]],
            "has_more": has_more,
        }

    def delete_expired(self, cutoff: str) -> int:
        """Delete messages timestamped (ISO-8601 string) before `cutoff`.
        Returns the number of rows removed."""
        with self._lock:
            cursor = self._conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
            self._conn.commit()
            return cursor.rowcount

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
