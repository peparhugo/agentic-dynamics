import sqlite3
import threading
import uuid
from datetime import datetime, timezone

_local = threading.local()


def get_db(db_path):
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(db_path, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def close_db():
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def init_db(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS urls (
            id TEXT PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_urls_code ON urls(code);

        CREATE TABLE IF NOT EXISTS clicks (
            id TEXT PRIMARY KEY,
            url_code TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            referer TEXT,
            FOREIGN KEY (url_code) REFERENCES urls(code)
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_url_code ON clicks(url_code);
        CREATE INDEX IF NOT EXISTS idx_clicks_timestamp ON clicks(timestamp);
    """)
    conn.commit()
    conn.close()


def insert_url(db_path, code, url):
    conn = get_db(db_path)
    row_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO urls (id, code, url, created_at) VALUES (?, ?, ?, ?)",
        (row_id, code, url, now),
    )
    conn.commit()
    return {"id": row_id, "code": code, "url": url, "created_at": now}


def get_url_by_code(db_path, code):
    conn = get_db(db_path)
    row = conn.execute("SELECT * FROM urls WHERE code = ?", (code,)).fetchone()
    if row is None:
        return None
    return dict(row)


def code_exists(db_path, code):
    conn = get_db(db_path)
    row = conn.execute("SELECT 1 FROM urls WHERE code = ?", (code,)).fetchone()
    return row is not None


def insert_click(db_path, code, ip, user_agent, referer):
    conn = get_db(db_path)
    row_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO clicks (id, url_code, timestamp, ip, user_agent, referer) VALUES (?, ?, ?, ?, ?, ?)",
        (row_id, code, now, ip, user_agent, referer),
    )
    conn.commit()


def get_click_count(db_path, code):
    conn = get_db(db_path)
    row = conn.execute(
        "SELECT COUNT(*) as count FROM clicks WHERE url_code = ?", (code,)
    ).fetchone()
    return row["count"]


def get_clicks(db_path, code, limit=100, offset=0):
    conn = get_db(db_path)
    rows = conn.execute(
        "SELECT * FROM clicks WHERE url_code = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (code, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_click_stats(db_path, code):
    conn = get_db(db_path)
    total = conn.execute(
        "SELECT COUNT(*) as count FROM clicks WHERE url_code = ?", (code,)
    ).fetchone()["count"]

    daily = conn.execute(
        """
        SELECT DATE(timestamp) as day, COUNT(*) as count
        FROM clicks WHERE url_code = ?
        GROUP BY day ORDER BY day DESC LIMIT 30
        """,
        (code,),
    ).fetchall()

    top_refs = conn.execute(
        """
        SELECT referer, COUNT(*) as count FROM clicks
        WHERE url_code = ? AND referer IS NOT NULL AND referer != ''
        GROUP BY referer ORDER BY count DESC LIMIT 10
        """,
        (code,),
    ).fetchall()

    return {
        "total_clicks": total,
        "daily": [dict(r) for r in daily],
        "top_referers": [dict(r) for r in top_refs],
    }
