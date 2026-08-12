"""
Repository pattern data access layer.

All SQL lives here, behind repository classes. Route handlers and the rest of
the application interact with the database exclusively through these
repositories.
"""

import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime


def get_db(db_path: str | None = None):
    conn = sqlite3.connect(db_path or os.environ.get("DATABASE", "todos.db"))
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in cols)


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        if not _column_exists(conn, "tasks", "owner_id"):
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        if not _column_exists(conn, "users", "email"):
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


class BaseRepository(ABC):
    """Abstract base class with common CRUD operations."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Name of the database table managed by this repository."""

    def _connect(self):
        return get_db(self.db_path)

    def get_by_id(self, row_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (row_id,)
            ).fetchone()
            return dict(row) if row else None

    def insert(self, **fields) -> dict:
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        values = tuple(fields.values())
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            return {**fields, "id": cursor.lastrowid}

    def update(self, row_id: int, **fields) -> dict | None:
        if self.get_by_id(row_id) is None:
            return None
        assignments = ", ".join(f"{column} = ?" for column in fields)
        params = tuple(fields.values()) + (row_id,)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                params,
            )
            conn.commit()
        return self.get_by_id(row_id)

    def delete(self, row_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (row_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


class UserRepository(BaseRepository):
    """Repository for the users table."""

    table_name = "users"

    def create(
        self, username: str, password_hash: str, email: str | None = None
    ) -> dict:
        return self.insert(
            username=username, password_hash=password_hash, email=email
        )

    def get_by_username(self, username: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None


class TaskRepository(BaseRepository):
    """Repository for the tasks table."""

    table_name = "tasks"

    def create(self, title: str, owner_id: int) -> dict:
        created_at = datetime.utcnow().isoformat()
        return self.insert(
            title=title,
            status="pending",
            created_at=created_at,
            owner_id=owner_id,
        )

    def list_for_owner(self, owner_id: int):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        task = self.get_for_owner(task_id, owner_id)
        if task is None:
            return None
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            params.append(owner_id)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} "
                    "WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.get_for_owner(task_id, owner_id)
