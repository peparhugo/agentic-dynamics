"""
Repository pattern for data access layer.

This module provides repository classes for accessing and manipulating data
from the SQLite database, abstracting direct SQL queries from route handlers.
"""

from abc import ABC, abstractmethod
import sqlite3
import os


class BaseRepository(ABC):
    """Abstract base repository with common database operations."""

    def __init__(self, database_path=None):
        self._database_path = database_path

    def get_db(self):
        """Get a database connection with row factory."""
        if self._database_path:
            db_path = self._database_path
        else:
            import app as app_module
            db_path = app_module.DATABASE
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def init_db(self):
        """Initialize database schema. Implemented by subclasses if needed."""
        pass


class UserRepository(BaseRepository):
    """Repository for user database operations."""

    def init_db(self):
        """Initialize users table if it doesn't exist."""
        with self.get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT
                )
            """)
            conn.commit()

    def create_user(self, username, password_hash, email):
        """
        Create a new user.

        Args:
            username: Unique username
            password_hash: Hashed password
            email: User email address (optional)

        Returns:
            User ID of the newly created user

        Raises:
            sqlite3.IntegrityError: If username already exists
        """
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            conn.commit()
            return cursor.lastrowid

    def get_user_by_username(self, username):
        """
        Get user by username.

        Args:
            username: The username to look up

        Returns:
            User row as dict-like object, or None if not found
        """
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return row

    def get_user_email(self, user_id):
        """
        Get email address for a user.

        Args:
            user_id: The user ID

        Returns:
            Email address as string, or None if not found
        """
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return row["email"] if row else None


class TaskRepository(BaseRepository):
    """Repository for task database operations."""

    def init_db(self):
        """Initialize tasks table if it doesn't exist."""
        with self.get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,
                    FOREIGN KEY (owner_id) REFERENCES users (id)
                )
            """)
            conn.commit()

    def create_task(self, title, status, created_at, owner_id):
        """
        Create a new task.

        Args:
            title: Task title
            status: Task status (default 'pending')
            created_at: ISO format timestamp
            owner_id: User ID of task owner

        Returns:
            Task ID of the newly created task
        """
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
                (title, status, created_at, owner_id),
            )
            conn.commit()
            return cursor.lastrowid

    def get_tasks_by_owner(self, owner_id):
        """
        Get all tasks for a user, ordered by created_at descending.

        Args:
            owner_id: User ID to get tasks for

        Returns:
            List of task rows as dict-like objects
        """
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,)
            ).fetchall()
        return rows

    def get_task_by_id_and_owner(self, task_id, owner_id):
        """
        Get a specific task by ID and verify ownership.

        Args:
            task_id: Task ID
            owner_id: Expected owner user ID

        Returns:
            Task row as dict-like object, or None if not found or not owned
        """
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return row

    def update_task(self, task_id, title, status):
        """
        Update a task's title and status.

        Args:
            task_id: Task ID to update
            title: New title
            status: New status

        Returns:
            True if task was updated, False if task not found
        """
        with self.get_db() as conn:
            cursor = conn.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id),
            )
            conn.commit()
            return cursor.rowcount > 0
