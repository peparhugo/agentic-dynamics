"""Repository implementations for the SQLite data store."""

from abc import ABC, abstractmethod
import sqlite3
from typing import Any


class BaseRepository(ABC):
    """Provide common SQLite CRUD operations for a repository."""

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Return the table managed by this repository."""

    def __init__(self, database: str):
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, values: dict[str, Any]) -> int:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            connection.commit()
            return cursor.lastrowid

    def get(self, record_id: int, fields: str = "*") -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT {fields} FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return dict(row) if row else None

    def list(self, fields: str = "*", where: str = "", params: tuple[Any, ...] = (), order_by: str = "") -> list[dict[str, Any]]:
        query = f"SELECT {fields} FROM {self.table_name}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def update(self, record_id: int, values: dict[str, Any], where: str = "", params: tuple[Any, ...] = ()) -> None:
        if not values:
            return
        assignments = ", ".join(f"{column} = ?" for column in values)
        query = f"UPDATE {self.table_name} SET {assignments} WHERE id = ?"
        query_params = tuple(values.values()) + (record_id,) + params
        if where:
            query = f"UPDATE {self.table_name} SET {assignments} WHERE id = ? AND {where}"
        with self._connect() as connection:
            connection.execute(query, query_params)
            connection.commit()

    def delete(self, record_id: int) -> None:
        with self._connect() as connection:
            connection.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            connection.commit()


class TaskRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "tasks"

    def create_task(self, title: str, owner_id: int, created_at: str) -> int:
        return self.create({
            "title": title,
            "status": "pending",
            "created_at": created_at,
            "owner_id": owner_id,
        })

    def get_tasks(self, owner_id: int) -> list[dict[str, Any]]:
        return self.list(
            fields="id, title, status, created_at",
            where="owner_id = ?",
            params=(owner_id,),
            order_by="created_at DESC",
        )

    def get_tasks_page(
        self, owner_id: int, cursor: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        where = "owner_id = ?"
        params: tuple[Any, ...] = (owner_id,)
        if cursor is not None:
            where += " AND id < ?"
            params += (cursor,)
        tasks = self.list(
            fields="id, title, status, created_at",
            where=where,
            params=params,
            order_by="id DESC",
        )
        tasks = tasks[: limit + 1]
        total = self.list(
            fields="COUNT(*) AS total",
            where="owner_id = ?",
            params=(owner_id,),
        )[0]["total"]
        return tasks, total

    def get_task(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        rows = self.list(
            fields="id, title, status, created_at",
            where="id = ? AND owner_id = ?",
            params=(task_id, owner_id),
        )
        return rows[0] if rows else None

    def update_task(self, task_id: int, owner_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        if self.get_task(task_id, owner_id) is None:
            return None
        self.update(task_id, values, where="owner_id = ?", params=(owner_id,))
        return self.get_task(task_id, owner_id)


class UserRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "users"

    def initialize_database(self, legacy_password_hash: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,"
                " password_hash TEXT NOT NULL, email TEXT)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,"
                " status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, owner_id INTEGER)"
            )
            user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
            task_columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "email" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
            if "owner_id" not in task_columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            legacy = connection.execute(
                "SELECT id FROM users WHERE username = ?", ("legacy",)
            ).fetchone()
            if legacy is None:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    ("legacy", legacy_password_hash),
                )
                legacy_id = cursor.lastrowid
            else:
                legacy_id = legacy[0]
            connection.execute("UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL", (legacy_id,))
            connection.commit()

    def create_user(self, username: str, password_hash: str, email: str | None) -> int | None:
        try:
            return self.create({"username": username, "password_hash": password_hash, "email": email})
        except sqlite3.IntegrityError:
            return None

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        rows = self.list(where="username = ?", params=(username,))
        return rows[0] if rows else None

    def get_email(self, user_id: int) -> str | None:
        user = self.get(user_id, fields="email, username")
        if user is None:
            return None
        return user["email"] or user["username"]
