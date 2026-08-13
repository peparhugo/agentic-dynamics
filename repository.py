"""
Repository pattern for data access layer.

Provides abstract base class and concrete implementations for database operations.
"""

from abc import ABC, abstractmethod
import sqlite3
import os


class BaseRepository(ABC):
    """Abstract base class for data repositories."""

    def __init__(self, database_path=None):
        """Initialize repository with database path."""
        self.database_path = database_path or os.environ.get("DATABASE", "tasks.db")

    def get_db(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def create(self, **kwargs):
        """Create a new record."""
        pass

    @abstractmethod
    def read(self, identifier):
        """Read a record by identifier."""
        pass

    @abstractmethod
    def update(self, identifier, **kwargs):
        """Update a record."""
        pass

    @abstractmethod
    def delete(self, identifier):
        """Delete a record."""
        pass

    @staticmethod
    def dict_from_row(row):
        """Convert sqlite3.Row to dict."""
        return dict(row) if row else None


class UserRepository(BaseRepository):
    """Repository for user data operations."""

    def create(self, username, password_hash, email=None):
        """Create a new user."""
        with self.get_db() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, password_hash, email)
                )
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                raise ValueError("username already exists")

    def read(self, user_id):
        """Get user by ID."""
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, email FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
        return self.dict_from_row(row)

    def read_by_username(self, username):
        """Get user by username."""
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, email FROM users WHERE username = ?",
                (username,)
            ).fetchone()
        return self.dict_from_row(row)

    def get_email(self, user_id):
        """Get user email by user_id."""
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT email FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()
        return self.dict_from_row(row)["email"] if row else None

    def update(self, user_id, **kwargs):
        """Update user record."""
        raise NotImplementedError("User update not implemented")

    def delete(self, user_id):
        """Delete user."""
        raise NotImplementedError("User delete not implemented")


class TaskRepository(BaseRepository):
    """Repository for task data operations."""

    def create(self, title, status, created_at, owner_id):
        """Create a new task."""
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
                (title, status, created_at, owner_id)
            )
            conn.commit()
            return cursor.lastrowid

    def read(self, task_id, owner_id=None):
        """Get task by ID. If owner_id is provided, check ownership."""
        with self.get_db() as conn:
            if owner_id is not None:
                row = conn.execute(
                    "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ? AND owner_id = ?",
                    (task_id, owner_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ?",
                    (task_id,)
                ).fetchone()
        return self.dict_from_row(row)

    def read_by_owner(self, owner_id):
        """Get all tasks for a user, ordered by created_at descending."""
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT id, title, status, created_at, owner_id FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,)
            ).fetchall()
        return [self.dict_from_row(row) for row in rows]

    def update(self, task_id, title=None, status=None):
        """Update task title and/or status."""
        with self.get_db() as conn:
            if title is not None and status is not None:
                conn.execute(
                    "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                    (title, status, task_id)
                )
            elif title is not None:
                conn.execute(
                    "UPDATE tasks SET title = ? WHERE id = ?",
                    (title, task_id)
                )
            elif status is not None:
                conn.execute(
                    "UPDATE tasks SET status = ? WHERE id = ?",
                    (status, task_id)
                )
            conn.commit()

    def delete(self, task_id):
        """Delete task."""
        with self.get_db() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()


class Database:
    """Database initialization and schema management."""

    def __init__(self, database_path=None):
        """Initialize database with path."""
        self.database_path = database_path or os.environ.get("DATABASE", "tasks.db")

    def get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
        """Initialize the database schema."""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    owner_id INTEGER,
                    FOREIGN KEY (owner_id) REFERENCES users(id)
                )
            """)
            conn.commit()
