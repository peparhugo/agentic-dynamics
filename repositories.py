"""SQLite repositories for task and user persistence."""

from abc import ABC
import sqlite3
from collections.abc import Callable
from typing import Any


ConnectionFactory = Callable[[], sqlite3.Connection]


class BaseRepository(ABC):
    """Provide common CRUD operations for a fixed database table."""

    table_name: str

    def __init__(self, connection_factory: ConnectionFactory):
        self.connection_factory = connection_factory

    def create(self, values: dict[str, Any]) -> int:
        columns = list(values)
        placeholders = ", ".join("?" for _ in columns)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})",
                [values[column] for column in columns],
            )
            return cursor.lastrowid

    def get_by_id(self, record_id: int) -> dict | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_all(self) -> list[dict]:
        with self.connection_factory() as connection:
            rows = connection.execute(f"SELECT * FROM {self.table_name}").fetchall()
        return [dict(row) for row in rows]

    def update(self, record_id: int, values: dict[str, Any]) -> bool:
        if not values:
            return self.get_by_id(record_id) is not None
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                [*values.values(), record_id],
            )
        return cursor.rowcount > 0

    def delete(self, record_id: int) -> bool:
        with self.connection_factory() as connection:
            cursor = connection.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
        return cursor.rowcount > 0


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def initialize(self) -> None:
        with self.connection_factory() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    owner_id INTEGER REFERENCES users(id)
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")

    def create_task(self, title: str, created_at: str, owner_id: int) -> dict:
        task_id = self.create({"title": title, "created_at": created_at, "owner_id": owner_id})
        return self.get_for_owner(task_id, owner_id)

    def list_page_for_owner(self, owner_id: int, cursor: int | None, limit: int) -> tuple[list[dict], int]:
        with self.connection_factory() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            conditions = ["owner_id = ?"]
            parameters: list[int] = [owner_id]
            if cursor is not None:
                conditions.append("id < ?")
                parameters.append(cursor)
            rows = connection.execute(
                f"SELECT id, title, status, created_at FROM tasks WHERE {' AND '.join(conditions)} "
                "ORDER BY id DESC LIMIT ?",
                [*parameters, limit],
            ).fetchall()
        return [dict(row) for row in rows], total

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row else None

    def update_for_owner(self, task_id: int, owner_id: int, values: dict[str, Any]) -> dict | None:
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        if values:
            assignments = ", ".join(f"{column} = ?" for column in values)
            with self.connection_factory() as connection:
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    [*values.values(), task_id, owner_id],
                )
        return self.get_for_owner(task_id, owner_id)


class UserRepository(BaseRepository):
    table_name = "users"

    def initialize(self) -> None:
        with self.connection_factory() as connection:
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
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
            if "email" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")

    def create_user(self, username: str, password_hash: str, email: str | None) -> int:
        return self.create({"username": username, "password_hash": password_hash, "email": email})

    def get_by_username(self, username: str) -> dict | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None

    def get_email(self, user_id: int) -> str | None:
        with self.connection_factory() as connection:
            row = connection.execute(
                "SELECT COALESCE(email, username) AS email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return row["email"] if row else None
