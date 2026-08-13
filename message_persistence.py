"""SQLite-based message persistence for notification history."""

import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger(__name__)


class MessagePersistence:
    """Handles persistent storage of messages in SQLite."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.environ.get("DATABASE_URL", "sqlite:///messages.db")
        self.db_path = self._parse_db_path(self.db_url)
        self._init_db()

    def _parse_db_path(self, db_url: str) -> str:
        """Parse database URL to get file path."""
        if db_url.startswith("sqlite:///"):
            return db_url.replace("sqlite:///", "")
        elif db_url.startswith("sqlite://"):
            return db_url.replace("sqlite://", "")
        return db_url

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize the database schema."""
        try:
            conn = self._get_connection()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_channel_timestamp ON messages(channel, timestamp)"
            )
            conn.commit()
            conn.close()
            logger.info(f"Initialized message database at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def store_message(
        self,
        channel: str,
        message_type: str,
        payload: dict,
        timestamp: Optional[str] = None
    ) -> int:
        """Store a message in the database."""
        try:
            conn = self._get_connection()
            timestamp = timestamp or datetime.utcnow().isoformat()
            cursor = conn.execute(
                """
                INSERT INTO messages (channel, type, payload, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (channel, message_type, json.dumps(payload), timestamp)
            )
            conn.commit()
            msg_id = cursor.lastrowid
            conn.close()
            return msg_id
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            raise

    def get_messages(
        self,
        channel: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[dict]:
        """Retrieve messages from the database."""
        try:
            conn = self._get_connection()

            if channel:
                cursor = conn.execute(
                    """
                    SELECT id, channel, type, payload, timestamp
                    FROM messages
                    WHERE channel = ?
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                    """,
                    (channel, limit, offset)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, channel, type, payload, timestamp
                    FROM messages
                    ORDER BY timestamp DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset)
                )

            rows = cursor.fetchall()
            conn.close()

            messages = []
            for row in rows:
                messages.append({
                    "id": row["id"],
                    "channel": row["channel"],
                    "type": row["type"],
                    "payload": json.loads(row["payload"]),
                    "timestamp": row["timestamp"]
                })
            return messages
        except Exception as e:
            logger.error(f"Error retrieving messages: {e}")
            return []

    def get_message_count(self, channel: Optional[str] = None) -> int:
        """Get total count of messages."""
        try:
            conn = self._get_connection()
            if channel:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM messages WHERE channel = ?",
                    (channel,)
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) as count FROM messages")
            count = cursor.fetchone()["count"]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0

    def clear_messages(self, channel: Optional[str] = None) -> None:
        """Clear messages from the database."""
        try:
            conn = self._get_connection()
            if channel:
                conn.execute("DELETE FROM messages WHERE channel = ?", (channel,))
            else:
                conn.execute("DELETE FROM messages")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error clearing messages: {e}")
