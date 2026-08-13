"""SQLite repositories for users and tasks."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timezone
import sqlite3
from typing import Any


ConnectionFactory = Callable[[], sqlite3.Connection]


def connect_database(database: str) -> sqlite3.Connection:
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class DuplicateUsernameError(Exception):
    """Raised when a username is already registered."""


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
        """Return fields accepted by create and update operations."""

    def create(self, **fields: Any) -> dict:
        invalid_fields = fields.keys() - self.writable_fields
        if invalid_fields or not fields:
            raise ValueError("invalid fields")

        columns = list(fields)
        placeholders = ", ".join("?" for _ in columns)
        with self.connection_factory() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({', '.join(columns)}) "
                f"VALUES ({placeholders})",
                [fields[column] for column in columns],
            )
            conn.commit()
            entity_id = cursor.lastrowid
        return self.get_by_id(entity_id)

    def get_by_id(self, entity_id: int) -> dict | None:
        with self.connection_factory() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (entity_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        with self.connection_factory() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table_name}").fetchall()
        return [dict(row) for row in rows]

    def update(self, entity_id: int, **fields: Any) -> dict | None:
        invalid_fields = fields.keys() - self.writable_fields
        if invalid_fields:
            raise ValueError("invalid fields")
        if not fields:
            return self.get_by_id(entity_id)

        columns = list(fields)
        assignments = ", ".join(f"{column} = ?" for column in columns)
        values = [fields[column] for column in columns]
        with self.connection_factory() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                [*values, entity_id],
            )
            conn.commit()
        return self.get_by_id(entity_id)

    def delete(self, entity_id: int) -> bool:
        with self.connection_factory() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (entity_id,)
            )
            conn.commit()
        return cursor.rowcount > 0


class UserRepository(BaseRepository):
    table_name = "users"
    writable_fields = frozenset({"username", "password_hash"})

    def initialize_schema(self) -> None:
        with self.connection_factory() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  username TEXT NOT NULL UNIQUE,"
                "  password_hash TEXT NOT NULL"
                ")"
            )
            conn.commit()

    def create_user(self, username: str, password_hash: str) -> dict:
        try:
            return self.create(username=username, password_hash=password_hash)
        except sqlite3.IntegrityError as error:
            raise DuplicateUsernameError from error

    def get_by_username(self, username: str) -> dict | None:
        with self.connection_factory() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None


class TaskRepository(BaseRepository):
    table_name = "tasks"
    writable_fields = frozenset({"title", "status", "created_at", "owner_id"})

    def initialize_schema(self) -> None:
        with self.connection_factory() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  title TEXT NOT NULL,"
                "  status TEXT NOT NULL DEFAULT 'pending',"
                "  created_at TEXT NOT NULL,"
                "  owner_id INTEGER REFERENCES users(id)"
                ")"
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                # Nullable ownership preserves tasks created before authentication.
                conn.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
            )
            conn.commit()

    def create_for_owner(self, title: str, owner_id: int) -> dict:
        return self.create(
            title=title,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            owner_id=owner_id,
        )

    def list_for_owner(
        self, owner_id: int, limit: int, cursor: int | None = None
    ) -> tuple[list[dict], int]:
        where = "owner_id = ?"
        parameters = [owner_id]
        if cursor is not None:
            where += " AND id < ?"
            parameters.append(cursor)

        with self.connection_factory() as conn:
            rows = conn.execute(
                f"SELECT * FROM tasks WHERE {where} "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (*parameters, limit + 1),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
        return [dict(row) for row in rows], total

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self.connection_factory() as conn:
            row = conn.execute(
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

        fields = {}
        if title is not None:
            fields["title"] = title
        if status is not None:
            fields["status"] = status
        if fields:
            columns = list(fields)
            assignments = ", ".join(f"{column} = ?" for column in columns)
            values = [fields[column] for column in columns]
            with self.connection_factory() as conn:
                conn.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    [*values, task_id, owner_id],
                )
                conn.commit()
        return self.get_for_owner(task_id, owner_id)
