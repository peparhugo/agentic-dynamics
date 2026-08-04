import aiosqlite
import config

CREATE_URLS = """
CREATE TABLE IF NOT EXISTS urls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    shortcode   TEXT    UNIQUE NOT NULL,
    target      TEXT    NOT NULL,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""

CREATE_CLICKS = """
CREATE TABLE IF NOT EXISTS clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    shortcode   TEXT    NOT NULL,
    timestamp   TEXT    DEFAULT (datetime('now')),
    ip          TEXT,
    referer     TEXT,
    user_agent  TEXT,
    FOREIGN KEY (shortcode) REFERENCES urls(shortcode)
);
"""

CREATE_INDEX = "CREATE INDEX IF NOT EXISTS idx_clicks_shortcode ON clicks(shortcode);"


async def init_db(db: aiosqlite.Connection):
    await db.execute(CREATE_URLS)
    await db.execute(CREATE_CLICKS)
    await db.execute(CREATE_INDEX)
    await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(config.DB_PATH)
    db.row_factory = aiosqlite.Row
    await init_db(db)
    return db


async def insert_url(db: aiosqlite.Connection, shortcode: str, target: str):
    await db.execute(
        "INSERT INTO urls (shortcode, target) VALUES (?, ?)",
        (shortcode, target),
    )
    await db.commit()


async def find_by_shortcode(db: aiosqlite.Connection, shortcode: str) -> dict | None:
    cursor = await db.execute(
        "SELECT shortcode, target, created_at FROM urls WHERE shortcode = ?",
        (shortcode,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def find_by_target(db: aiosqlite.Connection, target: str) -> dict | None:
    cursor = await db.execute(
        "SELECT shortcode, target, created_at FROM urls WHERE target = ?",
        (target,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def record_click(
    db: aiosqlite.Connection,
    shortcode: str,
    ip: str | None = None,
    referer: str | None = None,
    user_agent: str | None = None,
):
    await db.execute(
        "INSERT INTO clicks (shortcode, ip, referer, user_agent) VALUES (?, ?, ?, ?)",
        (shortcode, ip, referer, user_agent),
    )
    await db.commit()


async def get_click_stats(db: aiosqlite.Connection, shortcode: str) -> dict:
    cursor = await db.execute(
        "SELECT COUNT(*) AS total FROM clicks WHERE shortcode = ?",
        (shortcode,),
    )
    row = await cursor.fetchone()
    total = row["total"] if row else 0

    cursor = await db.execute(
        "SELECT referer, COUNT(*) AS count FROM clicks "
        "WHERE shortcode = ? AND referer IS NOT NULL "
        "GROUP BY referer ORDER BY count DESC LIMIT 10",
        (shortcode,),
    )
    referers = [dict(r) for r in await cursor.fetchall()]

    cursor = await db.execute(
        "SELECT ip, COUNT(*) AS count FROM clicks "
        "WHERE shortcode = ? AND ip IS NOT NULL "
        "GROUP BY ip ORDER BY count DESC LIMIT 10",
        (shortcode,),
    )
    ips = [dict(r) for r in await cursor.fetchall()]

    return {"shortcode": shortcode, "total_clicks": total, "top_referers": referers, "top_ips": ips}
