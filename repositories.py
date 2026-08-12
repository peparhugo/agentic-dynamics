"""Repository implementations for the todo application's SQLite data."""

from abc import ABC, abstractmethod
from datetime import datetime
import sqlite3
from typing import Any

from werkzeug.security import generate_password_hash


class UserAlreadyExistsError(Exception):
    """Raised when a user with the requested username already exists."""


class BaseRepository(ABC):
    """Provide connection handling and safe, table-oriented CRUD operations."""

    table_name: str

    def __init__(self, database: str):
        self.database = database

    @abstractmethod
    def initialize(self) -> None:
        """Create this repository's schema, including any required migrations."""

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)

    def get(self, record_id: int) -> sqlite3.Row | None:
        with self._connect() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def find_one(self, filters: dict[str, Any]) -> sqlite3.Row | None:
        where = " AND ".join(f"{column} = ?" for column in filters)
        with self._connect() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE {where}",
                tuple(filters.values()),
            ).fetchone()

    def list(self, filters: dict[str, Any] | None = None, order_by: str | None = None) -> list[sqlite3.Row]:
        filters = filters or {}
        clauses = " AND ".join(f"{column} = ?" for column in filters)
        where = f" WHERE {clauses}" if clauses else ""
        ordering = f" ORDER BY {order_by}" if order_by else ""
        with self._connect() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name}{where}{ordering}",
                tuple(filters.values()),
            ).fetchall()

    def update(self, record_id: int, values: dict[str, Any], filters: dict[str, Any] | None = None) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        conditions = {"id": record_id, **(filters or {})}
        where = " AND ".join(f"{column} = ?" for column in conditions)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE {where}",
                (*values.values(), *conditions.values()),
            )

    def delete(self, record_id: int) -> None:
        with self._connect() as connection:
            connection.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))


class UserRepository(BaseRepository):
    table_name = "users"

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "username TEXT NOT NULL UNIQUE, "
                "password_hash TEXT NOT NULL)"
            )

    def create_user(self, username: str, password: str) -> dict[str, Any]:
        try:
            user = self.create(
                {"username": username, "password_hash": generate_password_hash(password)}
            )
        except sqlite3.IntegrityError as error:
            raise UserAlreadyExistsError from error
        return {"id": user["id"], "username": user["username"]}

    def find_by_username(self, username: str) -> sqlite3.Row | None:
        return self.find_one({"username": username})

    def exists(self, user_id: int) -> bool:
        return self.find_one({"id": user_id}) is not None

    def get_email(self, user_id: int) -> str | None:
        user = self.get(user_id)
        return user["username"] if user else None


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "title TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending', "
                "created_at TEXT NOT NULL, "
                "owner_id INTEGER)"
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in ("id", "title", "status", "created_at")}

    def create_task(self, title: str, owner_id: int) -> dict[str, Any]:
        now = datetime.utcnow().isoformat()
        task = self.create(
            {"title": title, "status": "pending", "created_at": now, "owner_id": owner_id}
        )
        return self._serialize(task)

    def get_for_owner(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        task = self.find_one({"id": task_id, "owner_id": owner_id})
        return self._serialize(task) if task else None

    def list_for_owner(self, owner_id: int) -> list[dict[str, Any]]:
        return [
            self._serialize(task)
            for task in self.list({"owner_id": owner_id}, "created_at DESC")
        ]

    def list_for_owner_page(
        self, owner_id: int, cursor: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], int, bool]:
        clauses = ["owner_id = ?"]
        parameters: list[Any] = [owner_id]
        if cursor is not None:
            clauses.append("id < ?")
            parameters.append(cursor)
        where = " AND ".join(clauses)
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM tasks WHERE {where} ORDER BY id DESC LIMIT ?",
                (*parameters, limit + 1),
            ).fetchall()
        has_more = len(rows) > limit
        return [self._serialize(task) for task in rows[:limit]], total, has_more

    def update_for_owner(
        self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None
    ) -> dict[str, Any] | None:
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        values = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        if values:
            self.update(task_id, values, {"owner_id": owner_id})
        return self.get_for_owner(task_id, owner_id)
