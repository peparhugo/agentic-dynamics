"""Persistent SQLite storage layer.

Uses the standard library :mod:`sqlite3` so the project has no database
dependencies beyond Flask itself. Connections are opened per operation (with
``check_same_thread=False``) to remain safe inside Flask's threaded test
client.
"""

import datetime
import sqlite3
import threading
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code    TEXT    UNIQUE NOT NULL,
    original_url  TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code  TEXT NOT NULL,
    clicked_at  TEXT NOT NULL,
    ip          TEXT,
    user_agent  TEXT,
    FOREIGN KEY (short_code) REFERENCES urls(short_code)
);

CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON clicks(short_code);
"""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
            finally:
                conn.close()

    def code_exists(self, short_code: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT 1 FROM urls WHERE short_code = ?", (short_code,)
                ).fetchone()
                return row is not None
            finally:
                conn.close()

    def insert_url(self, short_code: str, original_url: str) -> bool:
        """Insert a URL row; returns False if the code already exists."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO urls (short_code, original_url, created_at) "
                    "VALUES (?, ?, ?)",
                    (short_code, original_url, _now()),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def get_url(self, short_code: str) -> Optional[sqlite3.Row]:
        with self._lock:
            conn = self._connect()
            try:
                return conn.execute(
                    "SELECT * FROM urls WHERE short_code = ?", (short_code,)
                ).fetchone()
            finally:
                conn.close()

    def record_click(self, short_code: str, ip: Optional[str],
                     user_agent: Optional[str]) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    "INSERT INTO clicks (short_code, clicked_at, ip, user_agent) "
                    "VALUES (?, ?, ?, ?)",
                    (short_code, _now(), ip, user_agent),
                )
                conn.commit()
            finally:
                conn.close()

    def click_count(self, short_code: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM clicks WHERE short_code = ?",
                    (short_code,),
                ).fetchone()
                return int(row["n"])
            finally:
                conn.close()

    def recent_clicks(self, short_code: str, limit: int = 10):
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT clicked_at, ip, user_agent FROM clicks "
                    "WHERE short_code = ? ORDER BY id DESC LIMIT ?",
                    (short_code, limit),
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()
