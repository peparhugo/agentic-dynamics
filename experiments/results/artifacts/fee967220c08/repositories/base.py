"""
BaseRepository — abstract base class for the Repository pattern.

Encapsulates the common SQLite plumbing (opening a connection, running a
query, converting rows to plain dicts) so concrete repositories only need
to describe *what* table/columns they work with, not *how* to talk to
SQLite. Route handlers should never touch ``sqlite3`` or write SQL
directly; they call methods on repository instances instead.
"""

from abc import ABC, abstractmethod
import sqlite3
from typing import Any, Callable, Iterable, Optional


class BaseRepository(ABC):
    """Common CRUD operations shared by all repositories.

    Subclasses must set ``table_name`` and may override ``primary_key``
    (defaults to ``"id"``). They must implement ``create`` and ``update``,
    since those operations are table-specific (different columns/rules),
    while ``get_by_id``, ``get_all`` and ``delete`` are provided generically.
    """

    table_name: str = ""
    primary_key: str = "id"

    def __init__(self, get_db: Callable[[], sqlite3.Connection]):
        """``get_db`` is a factory that returns a new sqlite3 connection.

        It is injected (rather than hardcoded) so repositories stay
        decoupled from *how*/*where* the database lives — tests can swap in
        a different database path/connection without touching this class.
        """
        self._get_db = get_db

    # ── low-level connection helpers ────────────────────────────────

    def _fetchone(self, query: str, params: Iterable[Any] = ()) -> Optional[dict]:
        with self._get_db() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def _fetchall(self, query: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def _execute(self, query: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._get_db() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor

    # ── generic CRUD operations ─────────────────────────────────────

    def get_by_id(self, id_: int) -> Optional[dict]:
        return self._fetchone(
            f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?",
            (id_,),
        )

    def get_all(self) -> list[dict]:
        return self._fetchall(f"SELECT * FROM {self.table_name}")

    def delete(self, id_: int) -> bool:
        cursor = self._execute(
            f"DELETE FROM {self.table_name} WHERE {self.primary_key} = ?",
            (id_,),
        )
        return cursor.rowcount > 0

    # ── table-specific operations (must be implemented by subclasses) ──

    @abstractmethod
    def create(self, **fields: Any) -> dict:
        """Insert a new record and return it as a dict."""
        raise NotImplementedError

    @abstractmethod
    def update(self, id_: int, **fields: Any) -> Optional[dict]:
        """Update an existing record; return the updated record, or None
        if no record with that id exists."""
        raise NotImplementedError
