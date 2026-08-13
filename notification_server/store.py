"""SQLite-backed history of messages that passed through the server."""
from __future__ import annotations

import json
import sqlite3
from typing import Any


class MessageStore:
    def __init__(self, path: str) -> None:
        self._path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )

    def save_message(
        self,
        msg_type: str,
        payload: dict[str, Any],
        timestamp: str,
        channel: str | None = None,
    ) -> int:
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), timestamp),
            )
            return cursor.lastrowid

    def get_messages(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_history(
        self,
        channel: str,
        since: str | None = None,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return up to `limit` messages for `channel`, oldest first.

        When `since` is given, only messages with a timestamp strictly after
        it are included. Fetches one extra row beyond `limit` to tell
        whether more matching messages exist without a separate COUNT query;
        that row is trimmed off before returning.
        """
        query = (
            "SELECT id, channel, type, payload, timestamp FROM messages "
            "WHERE channel = ?"
        )
        params: list[Any] = [channel]
        if since is not None:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        params.append(limit + 1)

        rows = self._conn.execute(query, params).fetchall()
        has_more = len(rows) > limit
        messages = [self._row_to_dict(row) for row in rows[:limit]]
        return messages, has_more

    def delete_older_than(self, cutoff: str) -> int:
        """Delete messages with a timestamp older than `cutoff` (ISO-8601 string). Returns the number deleted."""
        with self._conn:
            cursor = self._conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff,))
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
        self._conn.close()
