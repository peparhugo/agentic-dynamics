import aiosqlite
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "shortener.db"


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT NOT NULL UNIQUE,
                original_url TEXT NOT NULL,
                created_at REAL NOT NULL,
                click_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code);

            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT NOT NULL,
                timestamp REAL NOT NULL,
                ip TEXT NOT NULL DEFAULT '',
                user_agent TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (short_code) REFERENCES urls(short_code)
            );
            CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON clicks(short_code);
        """)
        await db.commit()
    finally:
        await db.close()


async def insert_url(short_code: str, original_url: str) -> dict:
    db = await get_db()
    try:
        now = time.time()
        cursor = await db.execute(
            "INSERT INTO urls (short_code, original_url, created_at, click_count) VALUES (?, ?, ?, 0)",
            (short_code, original_url, now),
        )
        await db.commit()
        return {
            "id": cursor.lastrowid,
            "short_code": short_code,
            "original_url": original_url,
            "created_at": now,
            "click_count": 0,
        }
    finally:
        await db.close()


async def get_url_by_code(short_code: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, short_code, original_url, created_at, click_count FROM urls WHERE short_code = ?",
            (short_code,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        await db.close()


async def code_exists(short_code: str) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM urls WHERE short_code = ?", (short_code,)
        )
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


async def increment_click_count(short_code: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE urls SET click_count = click_count + 1 WHERE short_code = ?",
            (short_code,),
        )
        await db.commit()
    finally:
        await db.close()


async def record_click(
    short_code: str, ip: str = "", user_agent: str = ""
) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO clicks (short_code, timestamp, ip, user_agent) VALUES (?, ?, ?, ?)",
            (short_code, time.time(), ip, user_agent),
        )
        await db.commit()
    finally:
        await db.close()


async def get_click_count(short_code: str) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM clicks WHERE short_code = ?",
            (short_code,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
    finally:
        await db.close()


async def get_analytics(short_code: str) -> dict:
    url = await get_url_by_code(short_code)
    if url is None:
        return {}
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT ip) as unique_ips FROM clicks WHERE short_code = ?",
            (short_code,),
        )
        row = await cursor.fetchone()
        total_clicks = row[0] if row else 0
        unique_ips = row[1] if row else 0

        cursor = await db.execute(
            "SELECT ip, COUNT(*) as cnt FROM clicks WHERE short_code = ? AND ip != '' GROUP BY ip ORDER BY cnt DESC LIMIT 10",
            (short_code,),
        )
        top_ips = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT timestamp FROM clicks WHERE short_code = ? ORDER BY timestamp DESC LIMIT 20",
            (short_code,),
        )
        recent = [dict(r) for r in await cursor.fetchall()]

        return {
            "short_code": short_code,
            "original_url": url["original_url"],
            "total_clicks": total_clicks,
            "unique_ips": unique_ips,
            "top_ips": top_ips,
            "recent_clicks": recent,
        }
    finally:
        await db.close()
