from abc import ABC, abstractmethod
import sqlite3
from typing import Optional, List, Dict, Any
import os


class BaseRepository(ABC):
    """Abstract base class for repository pattern implementations."""

    def get_db(self):
        """Get a database connection. Dynamically reads DATABASE env var."""
        db_path = os.environ.get("DATABASE", "todos.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def create(self, **kwargs) -> int:
        """Create a new record. Returns the ID of the created record."""
        pass

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """Get a record by ID."""
        pass

    @abstractmethod
    def get_all(self) -> List[Dict[str, Any]]:
        """Get all records."""
        pass

    @abstractmethod
    def update(self, id: int, **kwargs) -> bool:
        """Update a record. Returns True if successful."""
        pass

    @abstractmethod
    def delete(self, id: int) -> bool:
        """Delete a record. Returns True if successful."""
        pass


class TaskRepository(BaseRepository):
    """Repository for task database operations."""

    def create(self, title: str, status: str, created_at: str, owner_id: int) -> int:
        """Create a new task. Returns the task ID."""
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
                (title, status, created_at, owner_id),
            )
            conn.commit()
            return cursor.lastrowid

    def get_by_id(self, id: int, owner_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get a task by ID. If owner_id is provided, only return if the owner matches."""
        with self.get_db() as conn:
            if owner_id is not None:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                    (id, owner_id)
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
            return dict(row) if row else None

    def get_all(self, owner_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all tasks, optionally filtered by owner. Results are ordered by created_at DESC."""
        with self.get_db() as conn:
            if owner_id is not None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                    (owner_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def update(self, id: int, owner_id: Optional[int] = None, **kwargs) -> bool:
        """
        Update a task.
        If owner_id is provided, only update if the task belongs to that owner.
        Returns True if the task was found and updated.
        """
        task = self.get_by_id(id, owner_id)
        if task is None:
            return False

        with self.get_db() as conn:
            updates = []
            params = []
            if 'title' in kwargs and kwargs['title'] is not None:
                updates.append("title = ?")
                params.append(kwargs['title'])
            if 'status' in kwargs and kwargs['status'] is not None:
                updates.append("status = ?")
                params.append(kwargs['status'])

            if updates:
                params.append(id)
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()
        return True

    def delete(self, id: int, owner_id: Optional[int] = None) -> bool:
        """Delete a task. If owner_id is provided, only delete if the task belongs to that owner."""
        task = self.get_by_id(id, owner_id)
        if task is None:
            return False

        with self.get_db() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
            conn.commit()
        return True


class UserRepository(BaseRepository):
    """Repository for user database operations."""

    def create(self, username: str, password_hash: str, email: str) -> int:
        """Create a new user. Returns the user ID."""
        with self.get_db() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, password_hash, email),
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                raise

    def get_by_id(self, id: int) -> Optional[Dict[str, Any]]:
        """Get a user by ID."""
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (id,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get a user by username."""
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def get_email_by_id(self, id: int) -> Optional[str]:
        """Get user email by user ID."""
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE id = ?", (id,)
            ).fetchone()
            return row["email"] if row else None

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all users."""
        with self.get_db() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(r) for r in rows]

    def update(self, id: int, **kwargs) -> bool:
        """Update a user. Returns True if successful."""
        user = self.get_by_id(id)
        if user is None:
            return False

        with self.get_db() as conn:
            updates = []
            params = []
            if 'email' in kwargs and kwargs['email'] is not None:
                updates.append("email = ?")
                params.append(kwargs['email'])

            if updates:
                params.append(id)
                conn.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()
        return True

    def delete(self, id: int) -> bool:
        """Delete a user. Returns True if successful."""
        user = self.get_by_id(id)
        if user is None:
            return False

        with self.get_db() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (id,))
            conn.commit()
        return True
