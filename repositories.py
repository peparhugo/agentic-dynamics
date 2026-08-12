"""Repository pattern data access layer for the Task Management API.

All SQLite access is confined to these repository classes. Route handlers
only ever interact with repositories, never with raw SQL or connections.
"""

import sqlite3
from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Abstract base repository providing common CRUD operations.

    Subclasses must declare the ``table_name`` they operate on. The common
    ``create``, ``get_by_id``, ``get_all``, ``update`` and ``delete``
    operations are provided here.
    """

    table_name = abstractmethod(lambda self: None)

    def __init__(self, get_db):
        if not isinstance(get_db, type(lambda: None)):
            raise TypeError("get_db must be a callable returning a connection")
        self._get_db = get_db

    def _connection(self):
        return self._get_db()

    def get_by_id(self, record_id):
        with self._connection() as conn:
            return conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def get_all(self):
        with self._connection() as conn:
            return conn.execute(f"SELECT * FROM {self.table_name}").fetchall()

    def create(self, data):
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = tuple(data.values())
        with self._connection() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) "
                f"VALUES ({placeholders})",
                values,
            )
            conn.commit()
        return cursor.lastrowid

    def update(self, record_id, data):
        set_clause = ", ".join(f"{key} = ?" for key in data)
        values = tuple(data.values()) + (record_id,)
        with self._connection() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()

    def delete(self, record_id):
        with self._connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            conn.commit()
        return cursor.rowcount > 0


class TaskRepository(BaseRepository):
    """Repository for task records."""

    table_name = "tasks"

    def create_task(self, title, status, created_at, owner_id):
        task_id = self.create(
            {
                "title": title,
                "status": status,
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )
        return self.get_by_id(task_id)

    def get_for_owner(self, task_id, owner_id):
        with self._connection() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def list_for_owner(self, owner_id):
        with self._connection() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()

    def list_for_owner_page(self, owner_id, cursor=None, limit=20):
        query = "SELECT * FROM tasks WHERE owner_id = ? "
        params = [owner_id]
        if cursor is not None:
            query += "AND id < ? "
            params.append(cursor)
        query += "ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            return conn.execute(query, tuple(params)).fetchall()

    def count_for_owner(self, owner_id):
        with self._connection() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS total FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()["total"]


class UserRepository(BaseRepository):
    """Repository for user records."""

    table_name = "users"

    def create_user(self, username, password_hash, email):
        return self.create(
            {
                "username": username,
                "password_hash": password_hash,
                "email": email,
            }
        )

    def find_by_username(self, username):
        with self._connection() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
