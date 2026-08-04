import aiosqlite
import os
from typing import Optional

from .utils import generate_code, CODE_LENGTH, MAX_GENERATION_ATTEMPTS

DB_PATH = os.environ.get("SHORTENER_DB", os.path.join(os.path.dirname(__file__), "shortener.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    clicks INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    visited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip TEXT,
    user_agent TEXT,
    referer TEXT,
    FOREIGN KEY (code) REFERENCES urls(code) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analytics_code ON analytics(code);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    await db.executescript(SCHEMA)
    await db.commit()
    return db


async def create_url(db: aiosqlite.Connection, url: str) -> Optional[str]:
    for _ in range(MAX_GENERATION_ATTEMPTS):
        code = generate_code()
        try:
            await db.execute(
                "INSERT INTO urls (code, url) VALUES (?, ?)",
                (code, url),
            )
            await db.commit()
            return code
        except aiosqlite.IntegrityError:
            continue

    for length in range(CODE_LENGTH + 1, CODE_LENGTH + 4):
        for _ in range(MAX_GENERATION_ATTEMPTS):
            code = generate_code(length)
            try:
                await db.execute(
                    "INSERT INTO urls (code, url) VALUES (?, ?)",
                    (code, url),
                )
                await db.commit()
                return code
            except aiosqlite.IntegrityError:
                continue

    return None


async def get_url(db: aiosqlite.Connection, code: str) -> Optional[dict]:
    cursor = await db.execute("SELECT code, url, created_at, clicks FROM urls WHERE code = ?", (code,))
    row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def increment_clicks(db: aiosqlite.Connection, code: str) -> None:
    await db.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))
    await db.commit()


async def record_analytics(
    db: aiosqlite.Connection,
    code: str,
    ip: Optional[str],
    user_agent: Optional[str],
    referer: Optional[str],
) -> None:
    await db.execute(
        "INSERT INTO analytics (code, ip, user_agent, referer) VALUES (?, ?, ?, ?)",
        (code, ip, user_agent, referer),
    )
    await db.commit()


async def get_analytics(db: aiosqlite.Connection, code: str) -> Optional[dict]:
    url_row = await db.execute(
        "SELECT code, url, created_at, clicks FROM urls WHERE code = ?", (code,)
    )
    url_data = await url_row.fetchone()
    if url_data is None:
        return None

    result = dict(url_data)

    time_cursor = await db.execute(
        "SELECT visited_at, ip, user_agent, referer FROM analytics WHERE code = ? ORDER BY visited_at DESC LIMIT 100",
        (code,),
    )
    result["recent_visits"] = [dict(row) for row in await time_cursor.fetchall()]

    stats_cursor = await db.execute(
        "SELECT COUNT(*) as total, COUNT(DISTINCT ip) as unique_ips FROM analytics WHERE code = ?",
        (code,),
    )
    stats = await stats_cursor.fetchone()
    result["total_visits"] = stats["total"]
    result["unique_visitors"] = stats["unique_ips"]

    return result


async def list_urls(db: aiosqlite.Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    cursor = await db.execute(
        "SELECT code, url, created_at, clicks FROM urls ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return [dict(row) for row in await cursor.fetchall()]


async def delete_url(db: aiosqlite.Connection, code: str) -> bool:
    cursor = await db.execute("DELETE FROM urls WHERE code = ?", (code,))
    await db.commit()
    return cursor.rowcount > 0
