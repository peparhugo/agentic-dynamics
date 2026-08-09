import aiosqlite
from dataclasses import dataclass
from datetime import datetime, timezone

DB_PATH = "urlshortener.db"


@dataclass
class URLRecord:
    code: str
    url: str
    created_at: str
    clicks: int


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    return db


async def init_db() -> None:
    db = await get_db()
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            code TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            clicks INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS click_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            referrer TEXT,
            user_agent TEXT,
            ip TEXT,
            FOREIGN KEY (code) REFERENCES urls(code)
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_click_events_code ON click_events(code)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_click_events_timestamp ON click_events(timestamp)"
    )
    await db.commit()
    await db.close()


async def insert_url(code: str, url: str) -> None:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO urls (code, url, created_at, clicks) VALUES (?, ?, ?, 0)",
        (code, url, now),
    )
    await db.commit()
    await db.close()


async def get_url(code: str) -> URLRecord | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM urls WHERE code = ?", (code,))
    row = await cursor.fetchone()
    await db.close()
    if row is None:
        return None
    return URLRecord(
        code=row["code"],
        url=row["url"],
        created_at=row["created_at"],
        clicks=row["clicks"],
    )


async def increment_clicks(code: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,)
    )
    await db.commit()
    await db.close()


async def check_code_exists(code: str) -> bool:
    db = await get_db()
    cursor = await db.execute("SELECT 1 FROM urls WHERE code = ?", (code,))
    row = await cursor.fetchone()
    await db.close()
    return row is not None


async def record_click_event(
    code: str,
    referrer: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> None:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT INTO click_events (code, timestamp, referrer, user_agent, ip) "
        "VALUES (?, ?, ?, ?, ?)",
        (code, now, referrer, user_agent, ip),
    )
    await db.commit()
    await db.close()


async def get_click_stats(code: str) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) as total FROM click_events WHERE code = ?", (code,)
    )
    row = await cursor.fetchone()
    total_clicks = row["total"] if row else 0

    cursor = await db.execute(
        """
        SELECT date(timestamp) as day, COUNT(*) as count
        FROM click_events
        WHERE code = ?
        GROUP BY date(timestamp)
        ORDER BY day DESC
        LIMIT 30
        """,
        (code,),
    )
    daily = [
        {"date": r["day"], "count": r["count"]}
        for r in await cursor.fetchall()
    ]

    cursor = await db.execute(
        """
        SELECT referrer, COUNT(*) as count
        FROM click_events
        WHERE code = ? AND referrer IS NOT NULL AND referrer != ''
        GROUP BY referrer
        ORDER BY count DESC
        LIMIT 10
        """,
        (code,),
    )
    referrers = [
        {"referrer": r["referrer"], "count": r["count"]}
        for r in await cursor.fetchall()
    ]

    await db.close()
    return {
        "total_clicks": total_clicks,
        "daily_clicks": daily,
        "top_referrers": referrers,
    }
