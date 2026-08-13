"""SQLite repositories for the task-management API."""

from abc import ABC, abstractmethod
import sqlite3
from collections.abc import Callable, Mapping
from typing import Any


ConnectionFactory = Callable[[], sqlite3.Connection]


class BaseRepository(ABC):
    """Provides common CRUD operations for a SQLite table."""

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Return the table managed by this repository."""

    def __init__(self, connection_factory: ConnectionFactory):
        self.connection_factory = connection_factory

    def create(self, values: Mapping[str, Any]) -> int:
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values[column] for column in columns),
            )
            return cursor.lastrowid

    def get_by_id(self, record_id: int) -> dict[str, Any] | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_by_id(self, record_id: int, values: Mapping[str, Any]) -> bool:
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*values.values(), record_id),
            )
            return cursor.rowcount > 0

    def delete_by_id(self, record_id: int) -> bool:
        with self.connection_factory() as connection:
            cursor = connection.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            return cursor.rowcount > 0


class UserRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "users"

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None


class TaskRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "tasks"

    def get_for_owner(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def list_for_owner(self, owner_id: int) -> list[dict[str, Any]]:
        with self.connection_factory() as connection:
            rows = connection.execute(
                "SELECT id, title, status, created_at FROM tasks "
                "WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_notification_details(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                """
                SELECT tasks.status, tasks.title, users.username, users.email
                FROM tasks JOIN users ON users.id = tasks.owner_id
                WHERE tasks.id = ? AND tasks.owner_id = ?
                """,
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def update_for_owner(self, task_id: int, owner_id: int, values: Mapping[str, Any]) -> bool:
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                (*values.values(), task_id, owner_id),
            )
            return cursor.rowcount > 0


def initialize_database(connection_factory: ConnectionFactory) -> None:
    """Create application tables and migrate existing task databases."""
    with connection_factory() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        task_columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in task_columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        user_columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
