"""Repository classes for data access.

All SQLite queries live here so that route handlers never touch the database
directly.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Abstract base repository defining common CRUD operations."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def _connect(self):
        return self._connection_factory()

    @abstractmethod
    def create(self, **kwargs):
        """Insert a new record and return its identity/row."""

    @abstractmethod
    def get_by_id(self, entity_id):
        """Fetch a single record by primary key."""

    @abstractmethod
    def get_all(self):
        """Fetch all records."""

    @abstractmethod
    def update(self, entity_id, **kwargs):
        """Update a record by primary key."""

    @abstractmethod
    def delete(self, entity_id):
        """Delete a record by primary key."""


class TaskRepository(BaseRepository):
    """Data access for the ``tasks`` table."""

    def create(self, title, status, created_at, owner_id):
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id)"
                " VALUES (?, ?, ?, ?)",
                (title, status, created_at, owner_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return row

    def get_by_id(self, task_id, owner_id=None):
        with self._connect() as conn:
            if owner_id is None:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                    (task_id, owner_id),
                ).fetchone()
        return row

    def get_by_owner(self, owner_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
        return rows

    def get_all(self):
        with self._connect() as conn:
            return conn.execute("SELECT * FROM tasks").fetchall()

    def update(self, task_id, title, status):
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return row

    def delete(self, task_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()


class UserRepository(BaseRepository):
    """Data access for the ``users`` table."""

    def create(self, username, password_hash):
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
        return cur.lastrowid

    def get_by_id(self, user_id):
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, username, password_hash FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

    def find_by_username(self, username):
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

    def get_all(self):
        with self._connect() as conn:
            return conn.execute("SELECT id, username, password_hash FROM users").fetchall()

    def update(self, user_id, **kwargs):
        raise NotImplementedError

    def delete(self, user_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
