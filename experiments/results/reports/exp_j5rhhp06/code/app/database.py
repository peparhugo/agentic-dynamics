import sqlite3
import os
import time
from datetime import datetime, timezone

DB_PATH = os.environ.get("URL_SHORTENER_DB", "url_shortener.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT NOT NULL UNIQUE,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code);

        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT NOT NULL,
            clicked_at TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            referer TEXT,
            FOREIGN KEY (short_code) REFERENCES urls(short_code)
        );
        CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON clicks(short_code);
    """)
    conn.commit()
    conn.close()


def insert_url(short_code: str, original_url: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT INTO urls (short_code, original_url, created_at) VALUES (?, ?, ?)",
        (short_code, original_url, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_url_by_code(short_code: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT short_code, original_url, created_at FROM urls WHERE short_code = ?",
        (short_code,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def code_exists(short_code: str) -> bool:
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM urls WHERE short_code = ?", (short_code,)
    ).fetchone()
    conn.close()
    return row is not None


def record_click(
    short_code: str, ip_address: str | None = None,
    user_agent: str | None = None, referer: str | None = None
) -> None:
    conn = get_db()
    conn.execute(
        "INSERT INTO clicks (short_code, clicked_at, ip_address, user_agent, referer) "
        "VALUES (?, ?, ?, ?, ?)",
        (short_code, datetime.now(timezone.utc).isoformat(), ip_address, user_agent, referer),
    )
    conn.commit()
    conn.close()


def get_click_stats(short_code: str) -> dict:
    conn = get_db()
    total = conn.execute(
        "SELECT COUNT(*) as count FROM clicks WHERE short_code = ?", (short_code,)
    ).fetchone()["count"]

    recent = conn.execute(
        "SELECT clicked_at, ip_address, user_agent, referer FROM clicks "
        "WHERE short_code = ? ORDER BY clicked_at DESC LIMIT 10",
        (short_code,),
    ).fetchall()

    conn.close()
    return {
        "total_clicks": total,
        "recent_clicks": [dict(r) for r in recent],
    }
