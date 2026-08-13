"""
Repository pattern implementation for data access layer.

Abstracts database operations into repository classes with a common base.
"""

from abc import ABC, abstractmethod
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    """Abstract base class for all repositories."""

    def get_db(self):
        """Get a database connection with dynamic path resolution."""
        db_path = os.environ.get("DATABASE", "todos.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn


class UserRepository(BaseRepository):
    """Repository for user data access operations."""

    def create(self, username: str, password: str, email: str | None = None) -> dict | None:
        """Create a new user. Returns user dict or None if username already exists."""
        password_hash = generate_password_hash(password)
        with self.get_db() as conn:
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
                return None

    def get_by_username(self, username: str) -> dict | None:
        """Get a user by username."""
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None

    def get_by_id(self, user_id: int) -> dict | None:
        """Get a user by ID."""
        with self.get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None


class TaskRepository(BaseRepository):
    """Repository for task data access operations."""

    def create(self, owner_id: int, title: str) -> dict:
        """Create a new task."""
        with self.get_db() as conn:
            now = datetime.utcnow().isoformat()
            cursor = conn.execute(
                "INSERT INTO tasks (owner_id, title, status, created_at) VALUES (?, ?, 'pending', ?)",
                (owner_id, title, now),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "owner_id": owner_id,
                "title": title,
                "status": "pending",
                "created_at": now,
            }

    def get_for_user(self, owner_id: int) -> list:
        """Get all tasks for a user, ordered by created_at descending."""
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get(self, task_id: int, owner_id: int | None = None) -> dict | None:
        """Get a task by ID. Optionally filter by owner_id."""
        with self.get_db() as conn:
            if owner_id is not None:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                    (task_id, owner_id)
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        """Update a task. Returns updated task or None if not found."""
        task = self.get(task_id, owner_id)
        if task is None:
            return None

        with self.get_db() as conn:
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

        return self.get(task_id, owner_id)
