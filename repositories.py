"""
Repository pattern implementation for data access layer.
"""

from abc import ABC, abstractmethod
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class BaseRepository(ABC):
    """Abstract base class for all repositories."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_db(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def create(self, **kwargs):
        """Create a new entity."""
        pass

    @abstractmethod
    def get_by_id(self, entity_id: int):
        """Get entity by ID."""
        pass


class UserRepository(BaseRepository):
    """Repository for user data access."""

    def create(self, username: str, password: str, email: str | None = None) -> dict | None:
        """Create a new user."""
        password_hash = generate_password_hash(password)
        try:
            with self._get_db() as conn:
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
            return None

    def get_by_id(self, user_id: int) -> dict | None:
        """Get user by ID."""
        with self._get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_by_username(self, username: str) -> dict | None:
        """Get user by username."""
        with self._get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    def verify_password(self, password_hash: str, password: str) -> bool:
        """Verify a password against its hash."""
        return check_password_hash(password_hash, password)


class TaskRepository(BaseRepository):
    """Repository for task data access."""

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

    def get_by_id(self, task_id: int, owner_id: int) -> dict | None:
        """Get task by ID and owner ID."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def get_all_by_owner(self, owner_id: int) -> list:
        """Get all tasks for a user, ordered by creation date descending."""
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_paginated_by_owner(self, owner_id: int, cursor: int | None = None, limit: int = 20) -> tuple:
        """Get paginated tasks for a user, ordered by creation date descending.

        Returns (tasks, total_count, next_cursor).
        Cursor is the ID to start after; if None, starts from the beginning.
        """
        with self._get_db() as conn:
            # Get total count
            total_result = conn.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            total_count = total_result["count"] if total_result else 0

            # Build query
            if cursor is not None:
                query = "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?"
                params = (owner_id, cursor, limit + 1)
            else:
                query = "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?"
                params = (owner_id, limit + 1)

            rows = conn.execute(query, params).fetchall()
            tasks = [dict(r) for r in rows]

            # Determine if there's a next page
            next_cursor = None
            if len(tasks) > limit:
                tasks = tasks[:limit]
                next_cursor = tasks[-1]["id"] if tasks else None
            elif len(tasks) == 0:
                next_cursor = None
            else:
                next_cursor = None

            return tasks, total_count, next_cursor

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        """Update a task."""
        task = self.get_by_id(task_id, owner_id)
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
                params.append(owner_id)
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params
                )
                conn.commit()
        return self.get_by_id(task_id, owner_id)
