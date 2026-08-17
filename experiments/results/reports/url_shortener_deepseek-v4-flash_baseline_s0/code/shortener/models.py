import sqlite3
import threading
import time
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code        TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL,
    ip         TEXT,
    user_agent TEXT,
    referer    TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks(code, created_at);
"""


class Storage:
    """SQLite-backed persistent storage.

    A connection is opened per operation (or per transaction) so the store is
    safe to share across threads without extra locking.
    """

    def __init__(self, path):
        self.path = path
        self._lock = threading.RLock()
        # In-memory databases are per-connection, so share one connection.
        if path == ":memory:":
            self._shared = sqlite3.connect(":memory:", check_same_thread=False)
            self._shared.row_factory = sqlite3.Row
            with self._lock:
                self._shared.executescript(SCHEMA)
                self._shared.commit()
        else:
            self._shared = None
            with self.connect() as conn:
                conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        if self._shared is not None:
            with self._lock:
                yield self._shared
                self._shared.commit()
            return
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def code_exists(self, code):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM urls WHERE code = ?", (code,)
            ).fetchone()
        return row is not None

    def create_url(self, code, url):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO urls (code, url, created_at) VALUES (?, ?, ?)",
                (code, url, time.time()),
            )

    def get_url(self, code):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT code, url, created_at FROM urls WHERE code = ?", (code,)
            ).fetchone()
        return dict(row) if row else None

    def delete_url(self, code):
        with self.connect() as conn:
            conn.execute("DELETE FROM urls WHERE code = ?", (code,))
            conn.execute("DELETE FROM clicks WHERE code = ?", (code,))

    def record_click(self, code, ip, user_agent, referer):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO clicks (code, ip, user_agent, referer, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (code, ip, user_agent, referer, time.time()),
            )

    def click_stats(self, code):
        with self.connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM clicks WHERE code = ?", (code,)
            ).fetchone()["n"]
            unique_ips = conn.execute(
                "SELECT COUNT(DISTINCT ip) AS n FROM clicks WHERE code = ?",
                (code,),
            ).fetchone()["n"]
            recent = conn.execute(
                "SELECT ip, user_agent, referer, created_at FROM clicks "
                "WHERE code = ? ORDER BY created_at DESC LIMIT 20",
                (code,),
            ).fetchall()
            per_day = conn.execute(
                "SELECT date(created_at, 'unixepoch') AS day, COUNT(*) AS n "
                "FROM clicks WHERE code = ? GROUP BY day ORDER BY day DESC",
                (code,),
            ).fetchall()
        return {
            "total": total,
            "unique_ips": unique_ips,
            "recent_clicks": [dict(r) for r in recent],
            "clicks_per_day": {r["day"]: r["n"] for r in per_day},
        }
