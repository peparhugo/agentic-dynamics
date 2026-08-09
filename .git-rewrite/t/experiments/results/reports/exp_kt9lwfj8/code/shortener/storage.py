"""SQLite-backed storage for short links."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Link:
    code: str
    long_url: str
    created_at: float
    clicks: int


class Storage:
    """Thread-safe SQLite storage. Uses one connection per thread."""

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS links (
            code       TEXT PRIMARY KEY,
            long_url   TEXT NOT NULL,
            created_at REAL NOT NULL,
            clicks     INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_links_url ON links(long_url);
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._local = threading.local()
        with self._conn() as conn:
            conn.executescript(self._SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn

    def insert(self, code: str, long_url: str) -> bool:
        """Insert a link. Returns False if the code already exists."""
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO links (code, long_url, created_at) VALUES (?, ?, ?)",
                    (code, long_url, time.time()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get(self, code: str) -> Link | None:
        row = self._conn().execute(
            "SELECT * FROM links WHERE code = ?", (code,)
        ).fetchone()
        if row is None:
            return None
        return Link(row["code"], row["long_url"], row["created_at"], row["clicks"])

    def find_by_url(self, long_url: str) -> Link | None:
        row = self._conn().execute(
            "SELECT * FROM links WHERE long_url = ? LIMIT 1", (long_url,)
        ).fetchone()
        if row is None:
            return None
        return Link(row["code"], row["long_url"], row["created_at"], row["clicks"])

    def record_click(self, code: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE links SET clicks = clicks + 1 WHERE code = ?", (code,)
            )

    def delete(self, code: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM links WHERE code = ?", (code,))
        return cur.rowcount > 0
