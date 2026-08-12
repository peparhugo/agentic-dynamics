import os
import json
import aiosqlite


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///messages.db")


class MessageStore:
    def __init__(self, db_url: str | None = None):
        raw = db_url or DATABASE_URL
        if raw.startswith("sqlite:///"):
            raw = raw[len("sqlite:///"):]
        self._db_path = raw
        self._db: aiosqlite.Connection | None = None

    @property
    def db_path(self) -> str:
        return self._db_path

    async def connect(self) -> None:
        if self._db is not None:
            await self._db.close()
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        await self._db.commit()

    async def save_message(self, channel: str | None, msg_type: str,
                           payload: dict, timestamp: str) -> None:
        await self._db.execute(
            "INSERT INTO messages (channel, type, payload, timestamp) "
            "VALUES (?, ?, ?, ?)",
            (channel, msg_type, json.dumps(payload), timestamp),
        )
        await self._db.commit()

    async def get_messages(self, limit: int = 50, offset: int = 0) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT id, channel, type, payload, timestamp "
            "FROM messages ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
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

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None
