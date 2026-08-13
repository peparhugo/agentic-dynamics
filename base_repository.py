"""Abstract base repository providing common CRUD operations over a SQLite table.

Concrete repositories operate on a shared per-request sqlite3.Connection
(passed in at construction time, e.g. from Flask's `g`) rather than opening
their own connection, so they participate in the same transaction as the
rest of the request.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    @property
    @abstractmethod
    def table_name(self):
        """Name of the SQLite table this repository operates on."""

    def __init__(self, db):
        self.db = db

    def get_by_id(self, id_):
        return self.db.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (id_,)
        ).fetchone()

    def list_all(self, where=None, params=(), order_by=None):
        query = f"SELECT * FROM {self.table_name}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        return self.db.execute(query, params).fetchall()

    def delete(self, id_):
        self.db.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (id_,))
        self.db.commit()
