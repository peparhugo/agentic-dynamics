"""SQLite storage layer for the URL shortener."""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    long_url    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id      INTEGER NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    clicked_at  TEXT NOT NULL,
    ip          TEXT,
    user_agent  TEXT,
    referrer    TEXT
);

CREATE INDEX IF NOT EXISTS idx_clicks_url_id ON clicks(url_id);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    """Thread-safe wrapper around a SQLite connection."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- urls ------------------------------------------------------------

    def insert_url(self, code: str, long_url: str) -> dict:
        """Insert a mapping. Raises sqlite3.IntegrityError on duplicate code."""
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO urls (code, long_url, created_at) VALUES (?, ?, ?)",
                (code, long_url, _utcnow()),
            )
            self._conn.commit()
            return self.get_url_by_id(cur.lastrowid, _locked=True)

    def get_url_by_code(self, code: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM urls WHERE code = ?", (code,)
        ).fetchone()
        return dict(row) if row else None

    def get_url_by_id(self, url_id: int, _locked: bool = False) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM urls WHERE id = ?", (url_id,)
        ).fetchone()
        return dict(row) if row else None

    def find_by_long_url(self, long_url: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM urls WHERE long_url = ? ORDER BY id LIMIT 1", (long_url,)
        ).fetchone()
        return dict(row) if row else None

    def code_exists(self, code: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM urls WHERE code = ?", (code,)
        ).fetchone()
        return row is not None

    def delete_url(self, code: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM urls WHERE code = ?", (code,))
            self._conn.commit()
            return cur.rowcount > 0

    # -- clicks ----------------------------------------------------------

    def record_click(
        self,
        url_id: int,
        ip: str | None = None,
        user_agent: str | None = None,
        referrer: str | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO clicks (url_id, clicked_at, ip, user_agent, referrer)"
                " VALUES (?, ?, ?, ?, ?)",
                (url_id, _utcnow(), ip, user_agent, referrer),
            )
            self._conn.commit()

    def click_count(self, url_id: int) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM clicks WHERE url_id = ?", (url_id,)
        ).fetchone()
        return row["n"]

    def click_stats(self, url_id: int) -> dict:
        total = self.click_count(url_id)
        last_row = self._conn.execute(
            "SELECT clicked_at FROM clicks WHERE url_id = ?"
            " ORDER BY clicked_at DESC LIMIT 1",
            (url_id,),
        ).fetchone()
        referrers = self._conn.execute(
            "SELECT COALESCE(referrer, '(direct)') AS referrer, COUNT(*) AS n"
            " FROM clicks WHERE url_id = ? GROUP BY referrer ORDER BY n DESC",
            (url_id,),
        ).fetchall()
        by_day = self._conn.execute(
            "SELECT substr(clicked_at, 1, 10) AS day, COUNT(*) AS n"
            " FROM clicks WHERE url_id = ? GROUP BY day ORDER BY day",
            (url_id,),
        ).fetchall()
        return {
            "total_clicks": total,
            "last_clicked_at": last_row["clicked_at"] if last_row else None,
            "referrers": {r["referrer"]: r["n"] for r in referrers},
            "clicks_by_day": {r["day"]: r["n"] for r in by_day},
        }
