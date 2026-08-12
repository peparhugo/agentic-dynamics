"""Repository implementations for the SQLite-backed API."""

from abc import ABC, abstractmethod
from contextlib import closing
from datetime import datetime
import sqlite3
from typing import Any, Callable


ConnectionFactory = Callable[[], sqlite3.Connection]


class BaseRepository(ABC):
    """Common CRUD operations shared by table repositories."""

    table: str
    columns: tuple[str, ...]

    def __init__(self, connection_factory: ConnectionFactory):
        self.connection_factory = connection_factory

    @abstractmethod
    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        pass

    def create(self, values: dict[str, Any]) -> dict[str, Any]:
        fields = tuple(values)
        placeholders = ", ".join("?" for _ in fields)
        with closing(self.connection_factory()) as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table} ({', '.join(fields)}) VALUES ({placeholders})",
                tuple(values[field] for field in fields),
            )
            conn.commit()
            row = conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return self._row_to_dict(row)

    def get(self, entity_id: int) -> dict[str, Any] | None:
        with closing(self.connection_factory()) as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (entity_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None

    def list(self) -> list[dict[str, Any]]:
        with closing(self.connection_factory()) as conn:
            rows = conn.execute(f"SELECT * FROM {self.table}").fetchall()
            return [self._row_to_dict(row) for row in rows]

    def update(self, entity_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        if not values:
            return self.get(entity_id)
        assignments = ", ".join(f"{field} = ?" for field in values)
        with closing(self.connection_factory()) as conn:
            cursor = conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                (*values.values(), entity_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
        return self.get(entity_id)

    def delete(self, entity_id: int) -> bool:
        with closing(self.connection_factory()) as conn:
            cursor = conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (entity_id,))
            conn.commit()
            return cursor.rowcount > 0


class TaskRepository(BaseRepository):
    table = "tasks"
    columns = ("id", "title", "status", "created_at", "owner_id")

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def create_task(self, title: str, owner_id: int | None = None) -> dict[str, Any]:
        return self.create({
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "owner_id": owner_id,
        })

    def list_tasks(self, owner_id: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tasks"
        params: tuple[Any, ...] = ()
        if owner_id is not None:
            query += " WHERE owner_id = ?"
            params = (owner_id,)
        query += " ORDER BY created_at DESC"
        with closing(self.connection_factory()) as conn:
            return [self._row_to_dict(row) for row in conn.execute(query, params).fetchall()]

    def get_task(self, task_id: int, owner_id: int | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM tasks WHERE id = ?"
        params: tuple[Any, ...] = (task_id,)
        if owner_id is not None:
            query += " AND owner_id = ?"
            params += (owner_id,)
        with closing(self.connection_factory()) as conn:
            row = conn.execute(query, params).fetchone()
            return self._row_to_dict(row) if row else None

    def update_task(self, task_id: int, title: str | None = None,
                    status: str | None = None, owner_id: int | None = None) -> dict[str, Any] | None:
        task = self.get_task(task_id, owner_id)
        if task is None:
            return None
        values = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        if values:
            where = "id = ?" if owner_id is None else "id = ? AND owner_id = ?"
            params = (*values.values(), task_id) if owner_id is None else (*values.values(), task_id, owner_id)
            with closing(self.connection_factory()) as conn:
                conn.execute(f"UPDATE tasks SET {', '.join(f'{k} = ?' for k in values)} WHERE {where}", params)
                conn.commit()
        return self.get_task(task_id, owner_id)


class UserRepository(BaseRepository):
    table = "users"
    columns = ("id", "username", "password_hash")

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def create_user(self, username: str, password_hash: str) -> dict[str, Any]:
        return self.create({"username": username, "password_hash": password_hash})

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with closing(self.connection_factory()) as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return self._row_to_dict(row) if row else None

    def get_auth_user(self, user_id: int) -> dict[str, Any] | None:
        with closing(self.connection_factory()) as conn:
            row = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_dict(row) if row else None


def initialize_database(connection_factory: ConnectionFactory) -> None:
    """Create the current schema and migrate databases made by the old API."""
    with closing(connection_factory()) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, owner_id INTEGER REFERENCES users(id))")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        conn.commit()
