"""SQLite-backed message history store."""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional


def _parse_database_path(database_url: str) -> str:
    if database_url == ":memory:":
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://"):]
    return database_url


class MessageStore:
    """Persist every published message so history survives restarts."""

    def __init__(self, database_url: str) -> None:
        self._lock = threading.Lock()
        self._path = _parse_database_path(database_url)
        self._conn = sqlite3.connect(
            self._path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute(
                "PRAGMA journal_mode=WAL;"
                if self._path != ":memory:"
                else ""
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "channel TEXT NOT NULL,"
                "type TEXT NOT NULL,"
                "payload TEXT NOT NULL,"
                "timestamp TEXT NOT NULL"
                ")"
            )

    def add(
        self,
        channel: str,
        message_type: str,
        payload: Optional[dict],
        timestamp: str,
    ) -> int:
        payload = payload if payload is not None else {}
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (channel, message_type, json.dumps(payload), timestamp),
            )
            row_id = cursor.lastrowid
        return row_id

    def query(self, limit: int = 50, offset: int = 0) -> list[dict]:
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, channel, type, payload, timestamp FROM messages "
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                }
            )
        return result

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
        return row["n"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
