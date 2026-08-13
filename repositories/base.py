"""
BaseRepository — common CRUD operations shared by all repositories.

Each repository is constructed with a `get_db` callable (a connection
factory) so it always talks to whatever database the caller currently
points at, rather than caching a connection or a DB path at construction
time.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    table_name = None

    def __init__(self, get_db):
        self.get_db = get_db

    @abstractmethod
    def create_schema(self, conn):
        """Create this repository's table(s) if they don't already exist."""
        raise NotImplementedError

    def find_by_id(self, record_id):
        with self.get_db() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def insert(self, **fields):
        columns = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        with self.get_db() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def delete(self, record_id):
        with self.get_db() as conn:
            conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            conn.commit()
