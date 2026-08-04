import sqlite3
from datetime import datetime
from typing import Optional, Tuple

DB_PATH = "urlshortener.db"
_cache: dict[str, str] = {}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            short_code TEXT PRIMARY KEY,
            original_url TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT NOT NULL,
            clicked_at TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            FOREIGN KEY(short_code) REFERENCES urls(short_code)
        )
        """
    )
    conn.commit()
    conn.close()


def store_url(short_code: str, original_url: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO urls(short_code, original_url, created_at) VALUES (?, ?, ?)",
        (short_code, str(original_url), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    _cache[short_code] = str(original_url)


def get_original_url(short_code: str) -> Optional[str]:
    conn = get_conn()
    row = conn.execute("SELECT original_url FROM urls WHERE short_code = ?", (short_code,)).fetchone()
    conn.close()
    if row:
        return row["original_url"]
    # Fallback to in-memory cache if not present in DB
    if short_code in _cache:
        return _cache[short_code]
    return None


def log_click(short_code: str, ip: str | None, user_agent: str | None) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO clicks(short_code, clicked_at, ip, user_agent) VALUES (?, ?, ?, ?)",
        (short_code, datetime.utcnow().isoformat(), ip, user_agent),
    )
    conn.commit()
    conn.close()


def get_total_clicks(short_code: str) -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) as c FROM clicks WHERE short_code = ?", (short_code,)).fetchone()
    conn.close()
    return int(row["c"]) if row else 0


def get_created_at(short_code: str) -> Optional[str]:
    conn = get_conn()
    row = conn.execute("SELECT created_at FROM urls WHERE short_code = ?", (short_code,)).fetchone()
    conn.close()
    return row["created_at"] if row else None


def get_last_click_at(short_code: str) -> Optional[str]:
    conn = get_conn()
    row = conn.execute(
        "SELECT MAX(clicked_at) as last FROM clicks WHERE short_code = ?",
        (short_code,),
    ).fetchone()
    conn.close()
    return row["last"] if row else None
