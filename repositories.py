"""
Repository pattern implementation for data access layer.

Abstracts all database operations away from route handlers.
"""

from abc import ABC, abstractmethod
import sqlite3
from datetime import datetime
import os


class BaseRepository(ABC):
    """Abstract base class for repository pattern."""

    def __init__(self, database_path: str = None):
        self._database_path = database_path

    def _get_db_path(self):
        """Get current database path, checking environment and app module."""
        if self._database_path:
            return self._database_path
        try:
            import app as app_module
            return getattr(app_module, "DATABASE", os.environ.get("DATABASE", "todos.db"))
        except ImportError:
            return os.environ.get("DATABASE", "todos.db")

    def _get_db(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self._get_db_path())
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def find_by_id(self, id: int) -> dict | None:
        """Find entity by id."""
        pass

    @abstractmethod
    def create(self, **kwargs) -> dict:
        """Create new entity."""
        pass


class UserRepository(BaseRepository):
    """Repository for user data access."""

    def find_by_id(self, user_id: int) -> dict | None:
        """Find user by id."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def find_by_username(self, username: str) -> dict | None:
        """Find user by username."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def create(self, username: str, password_hash: str, email: str | None = None) -> dict | tuple:
        """Create a new user. Returns user dict or (error, message) tuple."""
        with self._get_db() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, password_hash, email),
                )
                conn.commit()
                return {
                    "id": cursor.lastrowid,
                    "username": username,
                    "email": email,
                }
            except sqlite3.IntegrityError:
                return ("conflict_error", "username already exists")

    def get_email(self, user_id: int) -> str | None:
        """Get user email by user_id."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return row["email"] if row else None


class TaskRepository(BaseRepository):
    """Repository for task data access."""

    def find_by_id(self, task_id: int, owner_id: int) -> dict | None:
        """Find task by id and owner_id."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def find_all_by_owner(self, owner_id: int) -> list:
        """Find all tasks for a user, ordered by created_at DESC."""
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_paginated_by_owner(self, owner_id: int, cursor: str | None = None, limit: int = 20) -> dict:
        """Find tasks with cursor-based pagination.

        Returns: {data: [...], next_cursor: str|None, total: int}
        Cursor is the id of the last item from the previous page.
        """
        with self._get_db() as conn:
            # Get total count
            total_row = conn.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            total = total_row["count"] if total_row else 0

            # Fetch one extra to determine if there's a next page
            fetch_limit = limit + 1
            if cursor:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                    (owner_id, cursor, fetch_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                    (owner_id, fetch_limit),
                ).fetchall()

            data = [dict(r) for r in rows[:limit]]
            next_cursor = None
            if len(rows) > limit:
                next_cursor = str(rows[limit]["id"])

            return {
                "data": data,
                "next_cursor": next_cursor,
                "total": total,
            }

    def create(self, title: str, owner_id: int) -> dict:
        """Create a new task."""
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

    def update(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        """Update a task's title and/or status."""
        task = self.find_by_id(task_id, owner_id)
        if task is None:
            return None

        with self._get_db() as conn:
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
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()

        return self.find_by_id(task_id, owner_id)
