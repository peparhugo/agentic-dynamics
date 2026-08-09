"""SQLite-backed storage for short URLs.

Thread-safe: each operation opens a short-lived connection, and SQLite
handles cross-process locking. Suitable for a single-node deployment;
swap for a networked store (e.g. Postgres/Redis) behind the same
interface for horizontal scaling.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    code       TEXT PRIMARY KEY,
    long_url   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    clicks     INTEGER NOT NULL DEFAULT 0
);
"""


@dataclass(frozen=True)
class ShortUrl:
    code: str
    long_url: str
    created_at: str
    clicks: int


class CodeCollisionError(Exception):
    """Raised when inserting a code that already exists."""


class SQLiteStorage:
    def __init__(self, path: str):
        self.path = path
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def save(self, code: str, long_url: str) -> ShortUrl:
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO urls (code, long_url, created_at) VALUES (?, ?, ?)",
                    (code, long_url, created_at),
                )
        except sqlite3.IntegrityError as exc:
            raise CodeCollisionError(code) from exc
        return ShortUrl(code=code, long_url=long_url, created_at=created_at, clicks=0)

    def get(self, code: str) -> ShortUrl | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT code, long_url, created_at, clicks FROM urls WHERE code = ?",
                (code,),
            ).fetchone()
        return ShortUrl(**dict(row)) if row else None

    def find_by_url(self, long_url: str) -> ShortUrl | None:
        """Return an existing mapping for this URL, if any (idempotent shorten)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT code, long_url, created_at, clicks FROM urls "
                "WHERE long_url = ? ORDER BY created_at LIMIT 1",
                (long_url,),
            ).fetchone()
        return ShortUrl(**dict(row)) if row else None

    def increment_clicks(self, code: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE urls SET clicks = clicks + 1 WHERE code = ?", (code,))

    def delete(self, code: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM urls WHERE code = ?", (code,))
        return cur.rowcount > 0
