"""
SQLite database module for message persistence.

Provides:
- Message storage with channel, type, payload, timestamp
- Async database operations
- Query for message history with limit and offset
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MessageDatabase:
    """SQLite database for storing messages."""

    def __init__(self, db_path: str = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to DATABASE_URL env var or ':memory:'
        """
        if db_path is None:
            db_path = os.getenv('DATABASE_URL', 'messages.db')

        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    def store_message(self, channel: str, msg_type: str, payload: dict, timestamp: str) -> int:
        """Store a message in the database.

        Args:
            channel: Message channel name
            msg_type: Message type
            payload: Message payload as dict
            timestamp: ISO format timestamp

        Returns:
            Message ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        payload_json = json.dumps(payload)

        cursor.execute('''
            INSERT INTO messages (channel, type, payload, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (channel, msg_type, payload_json, timestamp))

        msg_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"Message {msg_id} stored: channel={channel}, type={msg_type}")
        return msg_id

    def get_messages(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get messages from the database.

        Args:
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of message dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, channel, type, payload, timestamp
            FROM messages
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset))

        rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            msg_id, channel, msg_type, payload_json, timestamp = row
            messages.append({
                'id': msg_id,
                'channel': channel,
                'type': msg_type,
                'payload': json.loads(payload_json),
                'timestamp': timestamp
            })

        return messages

    def get_message_count(self) -> int:
        """Get total number of messages in database.

        Returns:
            Total message count
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM messages')
        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_messages_by_channel(self, channel: str, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get messages for a specific channel.

        Args:
            channel: Channel name to filter by
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of message dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, channel, type, payload, timestamp
            FROM messages
            WHERE channel = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        ''', (channel, limit, offset))

        rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            msg_id, ch, msg_type, payload_json, timestamp = row
            messages.append({
                'id': msg_id,
                'channel': ch,
                'type': msg_type,
                'payload': json.loads(payload_json),
                'timestamp': timestamp
            })

        return messages

    def clear_messages(self):
        """Clear all messages from database. Useful for testing."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages')
        conn.commit()
        conn.close()
        logger.info("All messages cleared from database")
