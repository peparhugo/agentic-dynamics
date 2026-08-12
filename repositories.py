"""Repository pattern data access layer for the task management API.

All SQLite access lives in this module. Route handlers and other
application code interact with repositories instead of issuing raw SQL.
"""

from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Abstract base repository providing common CRUD operations.

    Concrete subclasses declare the table they manage and how to convert
    a database row into a public-facing dictionary.
    """

    def __init__(self, db_factory):
        self.db_factory = db_factory

    @property
    @abstractmethod
    def table(self):
        """Name of the database table managed by this repository."""

    @abstractmethod
    def to_dict(self, row):
        """Convert a database row into a public-facing dictionary."""

    def _get_conn(self):
        return self.db_factory()

    def get(self, row_id):
        with self._get_conn() as conn:
            return conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (row_id,)
            ).fetchone()

    def list_all(self):
        with self._get_conn() as conn:
            return conn.execute(f"SELECT * FROM {self.table}").fetchall()

    def create(self, **fields):
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        values = tuple(fields.values())
        with self._get_conn() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            return conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()

    def update(self, row_id, **fields):
        assignments = ", ".join(f"{column} = ?" for column in fields)
        values = tuple(fields.values()) + (row_id,)
        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?", values
            )
            conn.commit()
            return conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (row_id,)
            ).fetchone()

    def delete(self, row_id):
        with self._get_conn() as conn:
            conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (row_id,))
            conn.commit()
        return None


class UserRepository(BaseRepository):
    """Repository for the users table."""

    @property
    def table(self):
        return "users"

    def to_dict(self, row):
        return {
            "id": row["id"],
            "username": row["username"],
        }

    def find_by_username(self, username):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()


class TaskRepository(BaseRepository):
    """Repository for the tasks table."""

    @property
    def table(self):
        return "tasks"

    def to_dict(self, row):
        return {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "created_at": row["created_at"],
            "owner_id": row["owner_id"],
        }

    def find_by_owner(self, owner_id):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()

    def find_by_owner_paginated(self, owner_id, cursor=None, limit=20):
        with self._get_conn() as conn:
            sql = "SELECT * FROM tasks WHERE owner_id = ?"
            params = [owner_id]
            if cursor is not None:
                sql += " AND id < ?"
                params.append(cursor)
            sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
            params.append(limit)
            return conn.execute(sql, params).fetchall()

    def count_by_owner(self, owner_id):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS count FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()["count"]

    def find_by_id_and_owner(self, task_id, owner_id):
        with self._get_conn() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
