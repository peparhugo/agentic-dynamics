"""
Abstract base repository providing the common CRUD contract shared by all
concrete repositories in this application.

Repositories don't own a database connection directly; instead they're
handed a zero-argument ``get_connection`` callable (typically ``db.get_db``)
so they always operate on whatever connection is appropriate for the
current context (e.g. Flask's per-request ``g.db``). This keeps repository
instances cheap to create once at import time and safe to reuse across
requests.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Common CRUD operations that every repository must implement.

    Subclasses set ``table_name`` and implement ``create``/``get_by_id``/
    ``get_all``/``update`` with whatever table-specific SQL and scoping
    rules they need. ``delete`` has a generic default implementation that
    subclasses may override if a table needs different semantics.
    """

    #: Name of the SQLite table this repository manages. Must be set by
    #: subclasses.
    table_name: str = None

    def __init__(self, get_connection):
        """``get_connection`` is a zero-arg callable returning a sqlite3
        connection, e.g. the Flask app's request-scoped ``get_db``."""
        self._get_connection = get_connection

    @property
    def db(self):
        """The active sqlite3 connection, resolved lazily on each access."""
        return self._get_connection()

    @abstractmethod
    def create(self, **fields):
        """Insert a new row and return it as a dict."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, id_):
        """Fetch a single row by primary key, or ``None`` if not found."""
        raise NotImplementedError

    @abstractmethod
    def get_all(self, **filters):
        """Fetch all rows, optionally scoped/filtered by subclass-defined
        keyword arguments."""
        raise NotImplementedError

    @abstractmethod
    def update(self, id_, **fields):
        """Update a row by primary key and return the (possibly unchanged)
        updated row, or ``None`` if no such row exists."""
        raise NotImplementedError

    def delete(self, id_) -> None:
        """Delete a row by primary key. Generic default using ``table_name``."""
        self.db.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (id_,))
        self.db.commit()

    @staticmethod
    def _row_to_dict(row):
        """Convert a ``sqlite3.Row`` (or ``None``) into a plain ``dict``."""
        return dict(row) if row is not None else None
