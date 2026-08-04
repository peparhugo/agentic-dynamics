import sqlite3
import time
from typing import Optional

from config import Config
from models import ShortURL


class Storage:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or Config.DB_PATH
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._migrate()

    def _migrate(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                short_code TEXT PRIMARY KEY,
                original_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                access_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_urls_expires ON urls(expires_at)"
        )
        self._conn.commit()

    def insert(self, entry: ShortURL) -> None:
        self._conn.execute(
            "INSERT INTO urls (short_code, original_url, created_at, expires_at, access_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                entry.short_code,
                entry.original_url,
                entry.created_at,
                entry.expires_at,
                entry.access_count,
            ),
        )
        self._conn.commit()

    def get(self, short_code: str) -> Optional[ShortURL]:
        row = self._conn.execute(
            "SELECT * FROM urls WHERE short_code = ?", (short_code,)
        ).fetchone()
        if row is None:
            return None
        return ShortURL(
            short_code=row["short_code"],
            original_url=row["original_url"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            access_count=row["access_count"],
        )

    def increment_access(self, short_code: str) -> None:
        self._conn.execute(
            "UPDATE urls SET access_count = access_count + 1 WHERE short_code = ?",
            (short_code,),
        )
        self._conn.commit()

    def purge_expired(self) -> int:
        now = ShortURL.now_iso()
        cursor = self._conn.execute(
            "DELETE FROM urls WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        self._conn.commit()
        return cursor.rowcount

    def exists(self, short_code: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM urls WHERE short_code = ?", (short_code,)
        ).fetchone()
        return row is not None

    def close(self):
        self._conn.close()
