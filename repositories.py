"""SQLite repositories for users and tasks."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
import sqlite3
from typing import Any


ConnectionFactory = Callable[[], sqlite3.Connection]


class RepositoryConflict(Exception):
    """Raised when persisted data violates a uniqueness constraint."""


class BaseRepository(ABC):
    """Base repository providing common CRUD operations."""

    def __init__(self, connection_factory: ConnectionFactory):
        self.connection_factory = connection_factory

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Return the repository's database table name."""

    @property
    @abstractmethod
    def writable_fields(self) -> frozenset[str]:
        """Return fields that may be inserted or updated."""

    @staticmethod
    def open_database(database: str) -> sqlite3.Connection:
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def initialize_database(connection_factory: ConnectionFactory) -> None:
        """Create the schema and migrate databases made by earlier versions."""
        with connection_factory() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "username TEXT NOT NULL UNIQUE, "
                "password_hash TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "title TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending', "
                "created_at TEXT NOT NULL, "
                "owner_id INTEGER REFERENCES users(id))"
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)")
            }
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
            )

    def create(self, values: Mapping[str, Any]) -> dict:
        fields = list(values)
        self._validate_fields(fields)
        placeholders = ", ".join("?" for _ in fields)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({', '.join(fields)}) "
                f"VALUES ({placeholders})",
                tuple(values[field] for field in fields),
            )
            item_id = cursor.lastrowid
        return self.get_by_id(item_id)  # type: ignore[arg-type, return-value]

    def get_by_id(self, item_id: int) -> dict | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (item_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all(self) -> list[dict]:
        with self.connection_factory() as connection:
            rows = connection.execute(f"SELECT * FROM {self.table_name}").fetchall()
        return [dict(row) for row in rows]

    def update(self, item_id: int, values: Mapping[str, Any]) -> dict | None:
        if self.get_by_id(item_id) is None:
            return None
        fields = list(values)
        self._validate_fields(fields)
        if fields:
            assignments = ", ".join(f"{field} = ?" for field in fields)
            parameters = tuple(values[field] for field in fields) + (item_id,)
            with self.connection_factory() as connection:
                connection.execute(
                    f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                    parameters,
                )
        return self.get_by_id(item_id)

    def delete(self, item_id: int) -> bool:
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (item_id,)
            )
        return cursor.rowcount > 0

    def _validate_fields(self, fields: list[str]) -> None:
        if not fields or not set(fields) <= self.writable_fields:
            raise ValueError("invalid repository fields")


class TaskRepository(BaseRepository):
    table_name = "tasks"
    writable_fields = frozenset({"title", "status", "created_at", "owner_id"})

    def create_for_owner(self, title: str, owner_id: int, created_at: str) -> dict:
        return self.create(
            {
                "title": title,
                "status": "pending",
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )

    def list_for_owner(self, owner_id: int) -> list[dict]:
        with self.connection_factory() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def page_for_owner(
        self, owner_id: int, cursor: int | None, limit: int
    ) -> tuple[list[dict], int, bool]:
        parameters: tuple[int, ...] = (owner_id,)
        cursor_clause = ""
        if cursor is not None:
            cursor_clause = "AND id < ? "
            parameters += (cursor,)
        with self.connection_factory() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                f"{cursor_clause}ORDER BY id DESC LIMIT ?",
                parameters + (limit + 1,),
            ).fetchall()
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
        return [dict(row) for row in rows[:limit]], total, len(rows) > limit

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def update_for_owner(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        values = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        if values:
            assignments = ", ".join(f"{field} = ?" for field in values)
            parameters = tuple(values.values()) + (task_id, owner_id)
            with self.connection_factory() as connection:
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    parameters,
                )
        return self.get_for_owner(task_id, owner_id)


class UserRepository(BaseRepository):
    table_name = "users"
    writable_fields = frozenset({"username", "password_hash"})

    def create_user(self, username: str, password_hash: str) -> dict:
        try:
            return self.create(
                {"username": username, "password_hash": password_hash}
            )
        except sqlite3.IntegrityError as error:
            raise RepositoryConflict from error

    def get_by_username(self, username: str) -> dict | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def get_identity(self, user_id: int) -> dict | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None
