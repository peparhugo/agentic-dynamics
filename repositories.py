"""
Data access layer using the Repository pattern.
Abstracts all database operations away from route handlers.
"""

from abc import ABC, abstractmethod
import sqlite3
import os
from contextlib import contextmanager


class BaseRepository(ABC):
    """Base repository with common CRUD operations."""

    @property
    def db_path(self):
        """Get the current database path from environment."""
        return os.environ.get("DATABASE", "tasks.db")

    @contextmanager
    def get_db(self):
        """Get a database connection with row factory enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def execute_query(self, query, params=None):
        """Execute a query that returns multiple rows."""
        with self.get_db() as conn:
            cursor = conn.execute(query, params or ())
            return cursor.fetchall()

    def execute_query_one(self, query, params=None):
        """Execute a query that returns a single row."""
        with self.get_db() as conn:
            cursor = conn.execute(query, params or ())
            return cursor.fetchone()

    def execute_update(self, query, params=None):
        """Execute an insert/update/delete query and commit."""
        with self.get_db() as conn:
            cursor = conn.execute(query, params or ())
            conn.commit()
            return cursor

    def get_by_id(self, entity_id):
        """Get an entity by ID. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_by_id")


class UserRepository(BaseRepository):
    """Repository for user data access."""

    def create_user(self, username, password_hash, email=None):
        """
        Create a new user.

        Returns:
            int: The ID of the newly created user

        Raises:
            sqlite3.IntegrityError: If username already exists
        """
        cursor = self.execute_update(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email if email else None)
        )
        return cursor.lastrowid

    def get_by_username(self, username):
        """Get a user by username."""
        return self.execute_query_one(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        )

    def get_by_id(self, user_id):
        """Get a user by ID."""
        return self.execute_query_one(
            "SELECT id, username, email FROM users WHERE id = ?",
            (user_id,)
        )

    def get_email_by_id(self, user_id):
        """Get a user's email by ID."""
        row = self.execute_query_one(
            "SELECT email FROM users WHERE id = ?",
            (user_id,)
        )
        return row['email'] if row else None


class TaskRepository(BaseRepository):
    """Repository for task data access."""

    def create_task(self, title, status, created_at, owner_id):
        """
        Create a new task.

        Returns:
            int: The ID of the newly created task
        """
        cursor = self.execute_update(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, status, created_at, owner_id)
        )
        return cursor.lastrowid

    def get_by_id(self, task_id, owner_id=None):
        """
        Get a task by ID.

        If owner_id is provided, ensures the task belongs to that user.
        """
        if owner_id is not None:
            return self.execute_query_one(
                "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id)
            )
        return self.execute_query_one(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ?",
            (task_id,)
        )

    def list_by_owner(self, owner_id):
        """Get all tasks for a specific owner, ordered by created_at descending."""
        return self.execute_query(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,)
        )

    def update_task(self, task_id, title=None, status=None):
        """
        Update a task's title and/or status.

        Returns:
            None
        """
        if title is not None and status is not None:
            self.execute_update(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id)
            )
        elif title is not None:
            self.execute_update(
                "UPDATE tasks SET title = ? WHERE id = ?",
                (title, task_id)
            )
        elif status is not None:
            self.execute_update(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id)
            )

    def get_task_with_owner(self, task_id):
        """Get a task without owner filtering. Used internally to check ownership."""
        return self.execute_query_one(
            "SELECT id, title, status, owner_id FROM tasks WHERE id = ?",
            (task_id,)
        )
