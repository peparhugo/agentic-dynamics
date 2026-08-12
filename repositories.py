"""
Repository pattern data access layer for the Task API.

Route handlers and auth helpers interact with repositories instead of
issuing raw SQL against SQLite directly.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Abstract base repository providing common CRUD operations."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    @property
    @abstractmethod
    def table(self):
        """Name of the database table managed by this repository."""

    def _connect(self):
        return self._connection_factory()

    def get(self, ident):
        """Fetch a single row by primary key, or None."""
        with self._connect() as conn:
            return conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (ident,)
            ).fetchone()

    def get_all(self):
        """Fetch all rows from the table."""
        with self._connect() as conn:
            return conn.execute(f"SELECT * FROM {self.table}").fetchall()

    def create(self, **fields):
        """Insert a row and return its new primary key."""
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            return cursor.lastrowid

    def update(self, ident, **fields):
        """Update the row with the given primary key."""
        if not fields:
            return
        assignments = ", ".join(f"{column} = ?" for column in fields)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                tuple(fields.values()) + (ident,),
            )
            conn.commit()

    def delete(self, ident):
        """Delete the row with the given primary key."""
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (ident,))
            conn.commit()


class TaskRepository(BaseRepository):
    """Data access for the tasks table."""

    table = "tasks"

    def get_owned(self, task_id, owner_id):
        """Fetch a task that belongs to the given owner, or None."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def list_for_owner(self, owner_id):
        """List a user's tasks ordered by creation time, newest first."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()


class UserRepository(BaseRepository):
    """Data access for the users table."""

    table = "users"

    def get_by_username(self, username):
        """Fetch a user by username, or None."""
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

    def find_id_by_username(self, username):
        """Return the primary key for a username, or None."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
        return row["id"] if row is not None else None
