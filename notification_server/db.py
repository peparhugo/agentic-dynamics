"""SQLite-backed message history store, queried via GET /messages."""

import json
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "messages.db"


def resolve_database_path(database_url=None) -> Path:
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        return DEFAULT_DB_PATH
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):])
    return Path(database_url)


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
