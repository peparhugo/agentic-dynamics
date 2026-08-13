from abc import ABC
import sqlite3
from typing import Any


class BaseRepository(ABC):
    """Shared SQLite CRUD helpers for a single table."""

    table_name: str

    def __init__(self, database: str):
        self.database = database

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, values: dict[str, Any]) -> dict:
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

    def get_by_id(self, record_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all(self, where: str = "", params: tuple = (), order_by: str = "") -> list[dict]:
        query = f"SELECT * FROM {self.table_name}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]

    def update(self, record_id: int, values: dict[str, Any], where: str = "", params: tuple = ()) -> dict | None:
        if not values:
            return self.get_by_id(record_id)
        assignments = ", ".join(f"{column} = ?" for column in values)
        condition = "id = ?"
        if where:
            condition += f" AND {where}"
        with self._connect() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE {condition}",
                (*values.values(), record_id, *params),
            )
        if where:
            records = self.get_all(f"id = ? AND {where}", (record_id, *params))
            return records[0] if records else None
        return self.get_by_id(record_id)

    def delete(self, record_id: int) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            return cursor.rowcount > 0


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  title TEXT NOT NULL,"
                "  status TEXT NOT NULL DEFAULT 'pending',"
                "  created_at TEXT NOT NULL,"
                "  owner_id INTEGER REFERENCES users(id)"
                ")"
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")

    def list_for_owner(self, owner_id: int) -> list[dict]:
        return self.get_all("owner_id = ?", (owner_id,), "created_at DESC")

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        tasks = self.get_all("id = ? AND owner_id = ?", (task_id, owner_id))
        return tasks[0] if tasks else None

    def update_for_owner(self, task_id: int, owner_id: int, values: dict[str, Any]) -> dict | None:
        return self.update(task_id, values, "owner_id = ?", (owner_id,))


class UserRepository(BaseRepository):
    table_name = "users"

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  username TEXT NOT NULL UNIQUE,"
                "  email TEXT,"
                "  password_hash TEXT NOT NULL"
                ")"
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
            if "email" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
                connection.execute("UPDATE users SET email = username WHERE email IS NULL")

    def create_user(self, username: str, email: str, password_hash: str) -> dict | None:
        try:
            user = self.create({"username": username, "email": email, "password_hash": password_hash})
        except sqlite3.IntegrityError:
            return None
        return {"id": user["id"], "username": user["username"]}

    def get_by_username(self, username: str) -> dict | None:
        users = self.get_all("username = ?", (username,))
        return users[0] if users else None
