import sqlite3
import time
from contextlib import contextmanager

from .codes import code_for_id


SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    destination TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    click_count INTEGER NOT NULL DEFAULT 0,
    last_clicked_at TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER NOT NULL REFERENCES urls(id) ON DELETE CASCADE,
    clicked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    visitor_hash TEXT NOT NULL,
    referrer TEXT,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS clicks_url_id_idx ON clicks(url_id, id DESC);

CREATE TABLE IF NOT EXISTS rate_limits (
    client_key TEXT PRIMARY KEY,
    window_start INTEGER NOT NULL,
    request_count INTEGER NOT NULL
);
"""


class Storage:
    def __init__(self, database: str):
        self.database = database

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(SCHEMA)
            connection.execute("PRAGMA journal_mode = WAL")

    def create_url(self, destination: str) -> dict:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT INTO urls (destination) VALUES (?)", (destination,)
            )
            code = code_for_id(cursor.lastrowid)
            connection.execute("UPDATE urls SET code = ? WHERE id = ?", (code, cursor.lastrowid))
            row = connection.execute(
                "SELECT code, destination, created_at FROM urls WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            connection.commit()
        return {"code": row["code"], "url": row["destination"], "created_at": row["created_at"]}

    def record_click(
        self,
        code: str,
        visitor_hash: str,
        referrer: str | None,
        user_agent: str,
    ) -> str | None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, destination FROM urls WHERE code = ?", (code,)
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute(
                """
                UPDATE urls
                SET click_count = click_count + 1,
                    last_clicked_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                WHERE id = ?
                """,
                (row["id"],),
            )
            connection.execute(
                """
                INSERT INTO clicks (url_id, visitor_hash, referrer, user_agent)
                VALUES (?, ?, ?, ?)
                """,
                (row["id"], visitor_hash, referrer, user_agent),
            )
            connection.commit()
            return row["destination"]

    def get_analytics(self, code: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, code, destination, created_at, click_count, last_clicked_at
                FROM urls WHERE code = ?
                """,
                (code,),
            ).fetchone()
            if row is None:
                return None
            unique_visitors = connection.execute(
                "SELECT COUNT(DISTINCT visitor_hash) FROM clicks WHERE url_id = ?",
                (row["id"],),
            ).fetchone()[0]
            clicks = connection.execute(
                """
                SELECT clicked_at, referrer, user_agent
                FROM clicks WHERE url_id = ? ORDER BY id DESC LIMIT 20
                """,
                (row["id"],),
            ).fetchall()

        return {
            "code": row["code"],
            "url": row["destination"],
            "created_at": row["created_at"],
            "click_count": row["click_count"],
            "last_clicked_at": row["last_clicked_at"],
            "unique_visitors": unique_visitors,
            "recent_clicks": [
                {
                    "clicked_at": click["clicked_at"],
                    "referrer": click["referrer"],
                    "user_agent": click["user_agent"],
                }
                for click in clicks
            ],
        }

    def check_rate_limit(self, client_key: str, limit: int, period: int) -> tuple[bool, int, float]:
        if limit < 1 or period < 1:
            raise ValueError("rate limit and window must be positive")

        now = time.time()
        window_start = int(now // period) * period
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT window_start, request_count FROM rate_limits WHERE client_key = ?",
                (client_key,),
            ).fetchone()
            if row is None or row["window_start"] != window_start:
                count = 1
                connection.execute(
                    """
                    INSERT INTO rate_limits (client_key, window_start, request_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(client_key) DO UPDATE SET
                        window_start = excluded.window_start,
                        request_count = 1
                    """,
                    (client_key, window_start),
                )
            elif row["request_count"] >= limit:
                count = row["request_count"]
            else:
                count = row["request_count"] + 1
                connection.execute(
                    "UPDATE rate_limits SET request_count = ? WHERE client_key = ?",
                    (count, client_key),
                )
            connection.commit()

        allowed = count <= limit
        return allowed, max(0, limit - count), window_start + period - now
