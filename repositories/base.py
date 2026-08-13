"""
BaseRepository — shared SQLite CRUD scaffolding for concrete repositories.

Each repository is constructed with a ``db_provider`` callable (rather than
a live connection) so that callers can swap the underlying database — as the
test suite does by reassigning ``app.DATABASE`` — without repositories
holding on to a stale connection or path.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    def __init__(self, db_provider):
        self.db_provider = db_provider

    def _fetch_one(self, query: str, params: tuple = ()) -> dict | None:
        with self.db_provider() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def _fetch_all(self, query: str, params: tuple = ()) -> list[dict]:
        with self.db_provider() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def _execute(self, query: str, params: tuple = ()):
        with self.db_provider() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor

    @abstractmethod
    def get_by_id(self, *args, **kwargs):
        """Fetch a single record by its primary key."""

    @abstractmethod
    def create(self, *args, **kwargs):
        """Insert a new record and return it as a dict."""
