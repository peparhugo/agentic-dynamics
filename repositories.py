"""
Repository layer — encapsulates all direct SQLite access.

Repositories are constructed with a connection-factory callable (in practice
app.get_db) rather than a fixed database path, so the underlying database
file can still be swapped at runtime the way tests do via app.DATABASE.
"""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime


class BaseRepository(ABC):
    def __init__(self, get_db):
        self._get_db = get_db

    @property
    @abstractmethod
    def table(self) -> str:
        """Name of the table this repository manages."""

    @staticmethod
    def _to_dict(row):
        return dict(row) if row is not None else None

    def find_by_id(self, record_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (record_id,)
            ).fetchone()
            return self._to_dict(row)

    def find_all(self) -> list[dict]:
        with self._get_db() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table}").fetchall()
            return [dict(r) for r in rows]

    def update(self, record_id: int, **fields) -> dict | None:
        if self.find_by_id(record_id) is None:
            return None
        if fields:
            with self._get_db() as conn:
                assignments = ", ".join(f"{col} = ?" for col in fields)
                params = [*fields.values(), record_id]
                conn.execute(
                    f"UPDATE {self.table} SET {assignments} WHERE id = ?", params
                )
                conn.commit()
        return self.find_by_id(record_id)

    def delete(self, record_id: int) -> None:
        with self._get_db() as conn:
            conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (record_id,))
            conn.commit()

    @abstractmethod
    def create(self, *args, **kwargs) -> dict | None:
        """Insert a new record and return it as a dict."""


class UserRepository(BaseRepository):
    table = "users"

    def create(self, username: str, password_hash: str) -> dict | None:
        with self._get_db() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return None
            return {"id": cursor.lastrowid, "username": username}

    def find_by_username(self, username: str) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return self._to_dict(row)


class TaskRepository(BaseRepository):
    table = "tasks"

    def create(self, title: str, owner_id: int) -> dict:
        with self._get_db() as conn:
            now = datetime.utcnow().isoformat()
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
                (title, now, owner_id),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "title": title,
                "status": "pending",
                "created_at": now,
                "owner_id": owner_id,
            }

    def find_by_owner(self, owner_id: int) -> list[dict]:
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update(self, task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        fields = {}
        if title is not None:
            fields["title"] = title
        if status is not None:
            fields["status"] = status
        return super().update(task_id, **fields)
