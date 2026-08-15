"""Repositories for the SQLite persistence layer."""

from abc import ABC, abstractmethod
import sqlite3
from typing import Any


class BaseRepository(ABC):
    """Common SQLite CRUD operations shared by concrete repositories."""

    table: str

    def __init__(self, database: str):
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    @abstractmethod
    def create_table(self) -> None:
        """Create the repository's table if it does not exist."""

    def create(self, values: dict[str, Any]) -> int:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            connection.commit()
            return cursor.lastrowid

    def get(self, record_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (record_id,)
            ).fetchone()

    def all(self) -> list[sqlite3.Row]:
        with self._connect() as connection:
            return connection.execute(f"SELECT * FROM {self.table}").fetchall()

    def update(self, record_id: int, values: dict[str, Any]) -> None:
        if not values:
            return
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                (*values.values(), record_id),
            )
            connection.commit()

    def delete(self, record_id: int) -> None:
        with self._connect() as connection:
            connection.execute(f"DELETE FROM {self.table} WHERE id = ?", (record_id,))
            connection.commit()


class UserRepository(BaseRepository):
    table = "users"

    def create_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "username TEXT NOT NULL UNIQUE, "
                "password_hash TEXT NOT NULL)"
            )
            connection.commit()

    def find_by_id(self, user_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()

    def find_by_username(self, username: Any) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()


class TaskRepository(BaseRepository):
    table = "tasks"

    def create_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "id INTEGER PRIMARY KEY, "
                "title TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending', "
                "created_at TEXT NOT NULL, "
                "owner_id INTEGER REFERENCES users(id))"
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            connection.commit()

    def create_task(self, title: str, created_at: str, owner_id: int | None) -> dict:
        with self._connect() as connection:
            next_id = connection.execute(
                "SELECT COALESCE(MAX(id) + 1, 0) FROM tasks"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO tasks (id, title, status, created_at, owner_id) "
                "VALUES (?, ?, 'pending', ?, ?)",
                (next_id, title, created_at, owner_id),
            )
            connection.commit()
            return dict(connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (next_id,)
            ).fetchone())

    def list_tasks(self, owner_id: int | None = None) -> list[dict]:
        with self._connect() as connection:
            if owner_id is None:
                rows = connection.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                    (owner_id,),
                ).fetchall()
            return [dict(row) for row in rows]

    def get_task(self, task_id: int, owner_id: int | None = None) -> dict | None:
        with self._connect() as connection:
            if owner_id is None:
                row = connection.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                    (task_id, owner_id),
                ).fetchone()
            return dict(row) if row else None

    def update_task(
        self, task_id: int, title: str | None, status: str | None,
        owner_id: int | None = None,
    ) -> dict | None:
        task = self.get_task(task_id, owner_id)
        if task is None:
            return None
        values = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        if values:
            assignments = ", ".join(f"{column} = ?" for column in values)
            params = list(values.values()) + [task_id]
            where = "id = ?"
            if owner_id is not None:
                where += " AND owner_id = ?"
                params.append(owner_id)
            with self._connect() as connection:
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE {where}", params
                )
                connection.commit()
        return self.get_task(task_id, owner_id)
