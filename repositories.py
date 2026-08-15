"""
Data access layer using the Repository pattern.
"""

import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class BaseRepository:
    """Abstract base repository with common CRUD operations."""

    def __init__(self, app_module):
        self.app_module = app_module

    def get_db(self):
        conn = sqlite3.connect(self.app_module.DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, query: str, params: tuple = ()):
        """Execute a query and return the cursor."""
        with self.get_db() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor

    def fetch_one(self, query: str, params: tuple = ()):
        """Fetch a single row."""
        with self.get_db() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple = ()):
        """Fetch multiple rows."""
        with self.get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]


class UserRepository(BaseRepository):
    """Repository for user data access."""

    def create(self, username: str, password: str, email: str | None = None) -> dict | None:
        """Create a new user."""
        password_hash = generate_password_hash(password)
        try:
            cursor = self.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            return {"id": cursor.lastrowid, "username": username, "email": email}
        except sqlite3.IntegrityError:
            return None

    def verify(self, username: str, password: str) -> dict | None:
        """Verify user credentials."""
        row = self.fetch_one(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        if row and check_password_hash(row["password_hash"], password):
            return {"id": row["id"], "username": row["username"], "email": row["email"]}
        return None

    def get_email(self, user_id: int) -> str | None:
        """Get user email by user ID."""
        row = self.fetch_one(
            "SELECT email FROM users WHERE id = ?", (user_id,)
        )
        return row["email"] if row else None


class TaskRepository(BaseRepository):
    """Repository for task data access."""

    def create(self, title: str, owner_id: int) -> dict:
        """Create a new task."""
        now = datetime.utcnow().isoformat()
        cursor = self.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, "pending", now, owner_id),
        )
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }

    def get_all(self, owner_id: int) -> list:
        """Get all tasks for a user, ordered by created_at descending."""
        return self.fetch_all(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )

    def get_by_id(self, task_id: int, owner_id: int) -> dict | None:
        """Get a specific task if owned by user."""
        return self.fetch_one(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        """Update a task and return the updated task."""
        task = self.get_by_id(task_id, owner_id)
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
            self.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", tuple(params)
            )

        return self.get_by_id(task_id, owner_id)
