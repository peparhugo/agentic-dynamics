import aiosqlite
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get("DB_PATH", "urls.db")


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            short_code TEXT PRIMARY KEY,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            click_count INTEGER NOT NULL DEFAULT 0,
            last_clicked_at TEXT
        )
        """
    )
    await db.commit()


async def insert_url(db: aiosqlite.Connection, short_code: str, original_url: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO urls (short_code, original_url, created_at) VALUES (?, ?, ?)",
        (short_code, original_url, now),
    )
    await db.commit()


async def get_url(db: aiosqlite.Connection, short_code: str) -> dict | None:
    async with db.execute(
        "SELECT short_code, original_url, created_at, click_count, last_clicked_at FROM urls WHERE short_code = ?",
        (short_code,),
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return {
                "short_code": row[0],
                "original_url": row[1],
                "created_at": row[2],
                "click_count": row[3],
                "last_clicked_at": row[4],
            }
        return None


async def increment_click(db: aiosqlite.Connection, short_code: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE urls SET click_count = click_count + 1, last_clicked_at = ? WHERE short_code = ?",
        (now, short_code),
    )
    await db.commit()
