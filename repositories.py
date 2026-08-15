"""
Repository layer for the task management API.

All SQLite access is confined to repository classes so that route
handlers never touch the database directly.
"""

import sqlite3
from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Abstract base repository with common CRUD operations."""

    def __init__(self, db_path):
        self.db_path = db_path

    @property
    @abstractmethod
    def table_name(self):
        """Name of the SQLite table this repository manages."""

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, record_id):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?",
                (record_id,),
            ).fetchone()
        return dict(row) if row else None

    def create(self, **values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) "
                f"VALUES ({placeholders})",
                tuple(values.values()),
            )
            conn.commit()
        return self.get_by_id(cursor.lastrowid)

    def update(self, record_id, **values):
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*values.values(), record_id),
            )
            conn.commit()
        return self.get_by_id(record_id)

    def delete(self, record_id):
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?",
                (record_id,),
            )
            conn.commit()

    def all(self):
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM {self.table_name}"
            ).fetchall()
        return [dict(row) for row in rows]


class TaskRepository(BaseRepository):
    """Repository for the tasks table."""

    @property
    def table_name(self):
        return "tasks"

    def list_by_owner(self, owner_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def find_by_owner(self, task_id, owner_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None


class UserRepository(BaseRepository):
    """Repository for the users table."""

    @property
    def table_name(self):
        return "users"

    def find_by_username(self, username):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return dict(row) if row else None
