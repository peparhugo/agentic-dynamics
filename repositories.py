"""Database repositories for users and tasks."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
import sqlite3


class DuplicateUserError(Exception):
    """Raised when a username violates the users table's unique constraint."""


class BaseRepository(ABC):
    """Provide connection management and common CRUD operations."""

    table = None
    columns = ()

    def __init__(self, database):
        self.database = database

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def create(self, values):
        fields = tuple(values)
        placeholders = ", ".join("?" for _ in fields)
        with self.connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table} ({', '.join(fields)}) VALUES ({placeholders})",
                tuple(values[field] for field in fields),
            )
            record_id = cursor.lastrowid
        return self.get(record_id)

    def get(self, record_id):
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def update(self, record_id, values):
        if not values:
            return self.get(record_id)
        assignments = ", ".join(f"{field} = ?" for field in values)
        with self.connection() as connection:
            connection.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                tuple(values.values()) + (record_id,),
            )
        return self.get(record_id)

    def delete(self, record_id):
        with self.connection() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table} WHERE id = ?", (record_id,)
            )
            return cursor.rowcount > 0

    @classmethod
    @abstractmethod
    def initialize_schema(cls, database):
        """Create or migrate the database schema."""


class UserRepository(BaseRepository):
    table = "users"
    columns = ("id", "username", "password_hash")

    def find_by_username(self, username):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def create(self, values):
        try:
            return super().create(values)
        except sqlite3.IntegrityError as error:
            raise DuplicateUserError from error

    @classmethod
    def initialize_schema(cls, database):
        with sqlite3.connect(database) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  username TEXT NOT NULL UNIQUE,"
                "  password_hash TEXT NOT NULL"
                ")"
            )


class TaskRepository(BaseRepository):
    table = "tasks"
    columns = ("id", "title", "status", "created_at", "owner_id")

    def for_owner(self, owner_id):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC",
                (owner_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def page_for_owner(self, owner_id, cursor=None, limit=20):
        with self.connection() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            if cursor is None:
                rows = connection.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                    (owner_id, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? AND id < ? "
                    "ORDER BY id DESC LIMIT ?",
                    (owner_id, cursor, limit),
                ).fetchall()
            data = [dict(row) for row in rows]
            next_cursor = str(data[-1]["id"]) if len(data) == limit else None
            return data, next_cursor, total

    def get_for_owner(self, task_id, owner_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update_for_owner(self, task_id, owner_id, values):
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        if values:
            assignments = ", ".join(f"{field} = ?" for field in values)
            with self.connection() as connection:
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    tuple(values.values()) + (task_id, owner_id),
                )
        return self.get_for_owner(task_id, owner_id)

    def get_any(self, task_id):
        return self.get(task_id)

    @classmethod
    def initialize_schema(cls, database):
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  title TEXT NOT NULL,"
                "  status TEXT NOT NULL DEFAULT 'pending',"
                "  created_at TEXT NOT NULL,"
                "  owner_id INTEGER REFERENCES users(id)"
                ")"
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )


def initialize_database(database):
    """Initialize repositories in dependency order."""
    UserRepository.initialize_schema(database)
    TaskRepository.initialize_schema(database)
