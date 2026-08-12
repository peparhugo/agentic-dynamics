"""
Repository layer for the Task Management API.

Extracts all SQLite access out of route handlers into repository classes
following the Repository pattern. BaseRepository provides common CRUD
operations; TaskRepository and UserRepository add domain-specific queries.
"""

import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Callable


class BaseRepository(ABC):
    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]):
        self._connection_factory = connection_factory

    @property
    @abstractmethod
    def table_name(self) -> str:
        ...

    def _connect(self) -> sqlite3.Connection:
        return self._connection_factory()

    def create(self, **fields) -> dict:
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            conn.commit()
            record_id = cursor.lastrowid
        return self.get_by_id(record_id)

    def get_by_id(self, record_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table_name}").fetchall()
        return [dict(row) for row in rows]

    def update(self, record_id: int, **fields) -> dict | None:
        if not fields:
            return self.get_by_id(record_id)
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*fields.values(), record_id),
            )
            conn.commit()
            updated = cursor.rowcount > 0
        return self.get_by_id(record_id) if updated else None

    def delete(self, record_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS total FROM {self.table_name}"
            ).fetchone()
        return row["total"]


class TaskRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "tasks"

    def list_by_owner(self, owner_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_by_owner_paginated(
        self, owner_id: int, cursor: int | None, limit: int
    ) -> list[dict]:
        """Return a page of tasks for an owner ordered by id DESC.

        When a cursor is provided only tasks with a smaller id are returned,
        giving stable, offset-free cursor pagination.
        """
        if cursor is not None:
            sql = (
                "SELECT * FROM tasks WHERE owner_id = ? AND id < ? "
                "ORDER BY id DESC LIMIT ?"
            )
            params: tuple = (owner_id, cursor, limit)
        else:
            sql = "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?"
            params = (owner_id, limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def count_by_owner(self, owner_id: int) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
        return row["total"]

    def get_by_id_and_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def update_for_owner(self, task_id: int, owner_id: int, **fields) -> bool:
        if not fields:
            return True
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                (*fields.values(), task_id, owner_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def delete_for_owner(self, task_id: int, owner_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            )
            conn.commit()
        return cursor.rowcount > 0


class UserRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "users"

    def get_by_username(self, username: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def create_user(self, username: str, password_hash: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
        return cursor.lastrowid
