"""Repository implementations for the application's SQLite data store."""

from abc import ABC, abstractmethod
from datetime import datetime
import sqlite3
from typing import Any


class BaseRepository(ABC):
    """Provide common CRUD operations for a SQLite table."""

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Return the table managed by this repository."""
        raise NotImplementedError

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create(self, **fields: Any) -> int:
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        cursor = self.connection.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(fields.values()),
        )
        self.connection.commit()
        return cursor.lastrowid

    def find_by_id(self, record_id: int):
        return self.connection.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
        ).fetchone()

    def find_one(self, **filters: Any):
        conditions = " AND ".join(f"{column} = ?" for column in filters)
        return self.connection.execute(
            f"SELECT * FROM {self.table_name} WHERE {conditions}",
            tuple(filters.values()),
        ).fetchone()

    def find_all(self, where: str = "", parameters: tuple[Any, ...] = (), order_by: str = ""):
        query = f"SELECT * FROM {self.table_name}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        return self.connection.execute(query, parameters).fetchall()

    def update(self, record_id: int, **fields: Any) -> None:
        assignments = ", ".join(f"{column} = ?" for column in fields)
        self.connection.execute(
            f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
            tuple(fields.values()) + (record_id,),
        )
        self.connection.commit()

    def delete(self, record_id: int) -> None:
        self.connection.execute(
            f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
        )
        self.connection.commit()


class UserRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "users"

    def create_user(self, username: str, password_hash: str, email: str) -> dict:
        user_id = self.create(
            username=username, password_hash=password_hash, email=email
        )
        return {"id": user_id, "username": username}

    def find_by_username(self, username: str):
        return self.find_one(username=username)


class TaskRepository(BaseRepository):
    @property
    def table_name(self) -> str:
        return "tasks"

    def create_task(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        task_id = self.create(
            title=title, status="pending", created_at=now, owner_id=owner_id
        )
        return {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }

    def list_for_owner(self, owner_id: int) -> list[dict]:
        rows = self.find_all(
            where="owner_id = ?", parameters=(owner_id,), order_by="created_at DESC"
        )
        return [dict(row) for row in rows]

    def find_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        row = self.find_one(id=task_id, owner_id=owner_id)
        return dict(row) if row else None

    def update_for_owner(
        self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None
    ) -> dict | None:
        task = self.find_for_owner(task_id, owner_id)
        if task is None:
            return None
        fields = {}
        if title is not None:
            fields["title"] = title
        if status is not None:
            fields["status"] = status
        if fields:
            assignments = ", ".join(f"{column} = ?" for column in fields)
            self.connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ? AND owner_id = ?",
                tuple(fields.values()) + (task_id, owner_id),
            )
            self.connection.commit()
        return self.find_for_owner(task_id, owner_id)


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create the tables and retain the application's existing migrations."""
    with connection as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
