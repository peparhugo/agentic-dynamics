import sqlite3
import threading
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    short_code TEXT PRIMARY KEY,
    original_url TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT NOT NULL,
    clicked_at TEXT NOT NULL,
    referrer TEXT,
    user_agent TEXT,
    ip TEXT,
    FOREIGN KEY (short_code) REFERENCES urls (short_code)
);
"""


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


class Storage:
    """Thread-safe SQLite-backed persistent storage for shortened URLs."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    def code_exists(self, short_code):
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM urls WHERE short_code = ?", (short_code,)
            )
            return cur.fetchone() is not None

    def create_url(self, short_code, original_url):
        with self._lock:
            self._conn.execute(
                "INSERT INTO urls (short_code, original_url, created_at) VALUES (?, ?, ?)",
                (short_code, original_url, _utcnow_iso()),
            )
            self._conn.commit()

    def get_url(self, short_code):
        with self._lock:
            cur = self._conn.execute(
                "SELECT short_code, original_url, created_at FROM urls WHERE short_code = ?",
                (short_code,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def delete_url(self, short_code):
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM urls WHERE short_code = ?", (short_code,)
            )
            self._conn.execute(
                "DELETE FROM clicks WHERE short_code = ?", (short_code,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def record_click(self, short_code, referrer=None, user_agent=None, ip=None):
        with self._lock:
            self._conn.execute(
                "INSERT INTO clicks (short_code, clicked_at, referrer, user_agent, ip) "
                "VALUES (?, ?, ?, ?, ?)",
                (short_code, _utcnow_iso(), referrer, user_agent, ip),
            )
            self._conn.commit()

    def click_count(self, short_code):
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) AS c FROM clicks WHERE short_code = ?", (short_code,)
            )
            return cur.fetchone()["c"]

    def analytics(self, short_code):
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) AS c FROM clicks WHERE short_code = ?", (short_code,)
            ).fetchone()["c"]

            by_day_rows = self._conn.execute(
                "SELECT substr(clicked_at, 1, 10) AS day, COUNT(*) AS c "
                "FROM clicks WHERE short_code = ? GROUP BY day ORDER BY day",
                (short_code,),
            ).fetchall()

            referrer_rows = self._conn.execute(
                "SELECT COALESCE(referrer, 'direct') AS referrer, COUNT(*) AS c "
                "FROM clicks WHERE short_code = ? GROUP BY referrer ORDER BY c DESC",
                (short_code,),
            ).fetchall()

            last_click = self._conn.execute(
                "SELECT clicked_at FROM clicks WHERE short_code = ? "
                "ORDER BY clicked_at DESC LIMIT 1",
                (short_code,),
            ).fetchone()

        return {
            "total_clicks": total,
            "clicks_by_day": {row["day"]: row["c"] for row in by_day_rows},
            "top_referrers": {row["referrer"]: row["c"] for row in referrer_rows},
            "last_click_at": last_click["clicked_at"] if last_click else None,
        }
