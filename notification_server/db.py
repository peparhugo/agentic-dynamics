"""SQLite-backed message history store, queried via GET /messages."""

import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "messages.db"
DEFAULT_MESSAGE_TTL_DAYS = 7


def resolve_database_path(database_url=None) -> Path:
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        return DEFAULT_DB_PATH
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):])
    return Path(database_url)


def resolve_message_ttl_days(message_ttl_days=None) -> float:
    if message_ttl_days is not None:
        return float(message_ttl_days)
    env_value = os.environ.get("MESSAGE_TTL_DAYS")
    if env_value:
        return float(env_value)
    return DEFAULT_MESSAGE_TTL_DAYS


class MessageStore:
    def __init__(self, path=DEFAULT_DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  channel TEXT,"
                "  type TEXT NOT NULL,"
                "  payload TEXT NOT NULL,"
                "  timestamp TEXT NOT NULL"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_channel_timestamp "
                "ON messages (channel, timestamp)"
            )

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_message(self, msg_type: str, payload: dict, timestamp: str, channel=None) -> dict:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (channel, type, payload, timestamp) VALUES (?, ?, ?, ?)",
                (channel, msg_type, json.dumps(payload), timestamp),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "channel": channel,
                "type": msg_type,
                "payload": payload,
                "timestamp": timestamp,
            }

    def list_messages(self, limit=50, offset=0) -> list:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def list_by_channel(self, channel: str, since=None, limit=50) -> tuple:
        """Chronological history for one channel, optionally restricted to
        messages after `since` (an ISO timestamp, exclusive). Returns
        (messages, has_more)."""
        query = "SELECT * FROM messages WHERE channel = ?"
        params = [channel]
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        query += " ORDER BY timestamp ASC, id ASC LIMIT ?"
        params.append(limit + 1)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        has_more = len(rows) > limit
        return [self._row_to_dict(row) for row in rows[:limit]], has_more

    def delete_older_than(self, cutoff_iso: str) -> int:
        """Delete every message with a timestamp before `cutoff_iso`.
        Returns the number of rows removed."""
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM messages WHERE timestamp < ?", (cutoff_iso,))
            conn.commit()
            return cursor.rowcount

    def clear(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "id": row["id"],
            "channel": row["channel"],
            "type": row["type"],
            "payload": json.loads(row["payload"]),
            "timestamp": row["timestamp"],
        }
