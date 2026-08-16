"""SQLite-backed message history store."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional


def _parse_database_path(database_url: str) -> str:
    if database_url == ":memory:":
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://"):]
    return database_url


def _to_utc_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp into an aware UTC datetime.

    Returns ``None`` when the value is missing or unparseable so callers can
    decide how to treat unknown timestamps.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }

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
        return [self._row_to_dict(row) for row in rows]

    def history(
        self,
        channel: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 50,
    ) -> tuple[list[dict], bool]:
        """Return messages in chronological order with a ``has_more`` flag.

        ``channel`` filters to a single channel (``None`` means all channels).
        ``since`` is an inclusive lower bound expressed as an ISO timestamp.
        Rows are scanned oldest-first so the result is always chronological,
        and one extra row is fetched to compute ``has_more``.
        """
        limit = max(0, int(limit))
        since_dt = _to_utc_datetime(since)
        with self._lock:
            if channel is None:
                rows = self._conn.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages "
                    "ORDER BY id ASC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT id, channel, type, payload, timestamp FROM messages "
                    "WHERE channel = ? ORDER BY id ASC",
                    (channel,),
                ).fetchall()

        messages: list[dict] = []
        for row in rows:
            dt = _to_utc_datetime(row["timestamp"])
            if since_dt is not None and (dt is None or dt < since_dt):
                continue
            messages.append(self._row_to_dict(row))

        has_more = len(messages) > limit
        return messages[:limit], has_more

    def cleanup_older_than(self, days: int) -> int:
        """Delete messages whose timestamp is older than ``days`` days."""
        days = max(0, int(days))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, timestamp FROM messages"
            ).fetchall()
            stale = []
            for row in rows:
                dt = _to_utc_datetime(row["timestamp"])
                if dt is not None and dt < cutoff:
                    stale.append(row["id"])
            if stale:
                self._conn.executemany(
                    "DELETE FROM messages WHERE id = ?",
                    [(message_id,) for message_id in stale],
                )
        return len(stale)

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()
        return row["n"]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
