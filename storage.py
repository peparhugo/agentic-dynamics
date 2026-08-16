"""SQLite persistence for notification history."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


def sqlite_path(database_url: str) -> str:
    """Convert a SQLite DATABASE_URL (or plain path) to a sqlite3 path."""
    if database_url == "sqlite:///:memory:":
        return ":memory:"
    if database_url.startswith("sqlite:////"):
        return "/" + database_url[len("sqlite:////") :]
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///") :]
    if database_url.startswith("sqlite://"):
        raise ValueError("DATABASE_URL must use sqlite:///path")
    return database_url


class MessageStore:
    def __init__(self, database_url: str = "sqlite:///:memory:") -> None:
        path = sqlite_path(database_url)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._connection:
            self._connection.execute(
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

    def save(self, message: dict[str, Any]) -> int:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (
                    message.get("channel"),
                    message["type"],
                    json.dumps(message["payload"], separators=(",", ":")),
                    message["timestamp"],
                ),
            )
            return int(cursor.lastrowid)

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages ORDER BY id DESC LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
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

    def close(self) -> None:
        self._connection.close()
