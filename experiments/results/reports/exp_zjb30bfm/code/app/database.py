import sqlite3
import threading
import time
from typing import Optional

DB_PATH = "url_shortener.db"

_local = threading.local()


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    return _local.conn


def init_db() -> None:
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            created_at REAL NOT NULL,
            click_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT NOT NULL,
            timestamp REAL NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            referer TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON clicks(short_code)
    """)
    conn.commit()


def code_exists(short_code: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM urls WHERE short_code = ?", (short_code,)
    ).fetchone()
    return row is not None


def insert_url(short_code: str, original_url: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO urls (short_code, original_url, created_at) VALUES (?, ?, ?)",
        (short_code, original_url, time.time()),
    )
    conn.commit()


def get_url(short_code: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT short_code, original_url, created_at, click_count FROM urls WHERE short_code = ?",
        (short_code,),
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def increment_click_count(short_code: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE urls SET click_count = click_count + 1 WHERE short_code = ?",
        (short_code,),
    )
    conn.commit()


def record_click(
    short_code: str, ip_address: str = None, user_agent: str = None, referer: str = None
) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO clicks (short_code, timestamp, ip_address, user_agent, referer) VALUES (?, ?, ?, ?, ?)",
        (short_code, time.time(), ip_address, user_agent, referer),
    )
    conn.commit()


def get_stats(short_code: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT short_code, original_url, created_at, click_count FROM urls WHERE short_code = ?",
        (short_code,),
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    click_rows = conn.execute(
        "SELECT timestamp, ip_address, user_agent, referer FROM clicks WHERE short_code = ? ORDER BY timestamp DESC",
        (short_code,),
    ).fetchall()
    result["clicks"] = [dict(r) for r in click_rows]
    return result
