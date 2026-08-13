"""
SQLite database for message persistence.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any
from contextlib import contextmanager


class MessageDatabase:
    """SQLite database for storing messages."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_channel
                ON messages (channel)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON messages (timestamp)
            """)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def store_message(self, channel: str, message_type: str,
                     payload: Dict[str, Any], timestamp: str) -> int:
        """Store a message in the database."""
        payload_json = json.dumps(payload)

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (channel, type, payload, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (channel, message_type, payload_json, timestamp)
            )
            conn.commit()
            return cursor.lastrowid

    def get_messages(self, channel: str | None = None,
                    limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get messages from the database."""
        with self._get_connection() as conn:
            if channel:
                cursor = conn.execute(
                    """
                    SELECT id, channel, type, payload, timestamp
                    FROM messages
                    WHERE channel = ?
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (channel, limit, offset)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, channel, type, payload, timestamp
                    FROM messages
                    ORDER BY id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                )

            rows = cursor.fetchall()
            messages = []
            for row in rows:
                messages.append({
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                })
            return messages

    def get_message_count(self, channel: str | None = None) -> int:
        """Get the total count of messages."""
        with self._get_connection() as conn:
            if channel:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM messages WHERE channel = ?",
                    (channel,)
                )
            else:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM messages"
                )

            result = cursor.fetchone()
            return result["count"]

    def get_messages_since(self, channel: str, since: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages from a specific channel since a timestamp."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, channel, type, payload, timestamp
                FROM messages
                WHERE channel = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                LIMIT ?
                """,
                (channel, since, limit)
            )

            rows = cursor.fetchall()
            messages = []
            for row in rows:
                messages.append({
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"],
                })
            return messages

    def delete_old_messages(self, days: int) -> int:
        """Delete messages older than specified days. Returns count of deleted messages."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM messages
                WHERE datetime(timestamp) < datetime('now', ? || ' days')
                """,
                (f"-{days}",)
            )
            conn.commit()
            return cursor.rowcount

    def clear_messages(self) -> None:
        """Clear all messages from the database (for testing)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages")
            conn.commit()
