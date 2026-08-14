"""Repository pattern data access layer.

All SQLite queries live in repository classes. Route handlers interact
with repositories instead of raw SQL.
"""

import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from werkzeug.security import generate_password_hash


def get_db():
    conn = sqlite3.connect(os.environ.get("DATABASE", "todos.db"))
    conn.row_factory = sqlite3.Row
    return conn


class BaseRepository(ABC):
    """Abstract base repository with common CRUD operations."""

    @property
    @abstractmethod
    def table(self) -> str:
        """Name of the database table this repository manages."""

    def __init__(self, db=None):
        self._db = db if db is not None else get_db()

    def _row_to_dict(self, row):
        return dict(row) if row is not None else None

    def _rows_to_dicts(self, rows):
        return [dict(r) for r in rows]

    def get_by_id(self, record_id: int, **scope) -> dict | None:
        """Fetch a single record by id, optionally scoped by extra columns."""
        query = f"SELECT * FROM {self.table} WHERE id = ?"
        params = [record_id]
        for column, value in scope.items():
            query += f" AND {column} = ?"
            params.append(value)
        with self._db:
            row = self._db.execute(query, params).fetchone()
        return self._row_to_dict(row)

    def get_many(self, *, order_by: str | None = None, **filters) -> list[dict]:
        """Fetch all records matching filters, optionally ordered."""
        query = f"SELECT * FROM {self.table}"
        params = []
        if filters:
            clauses = [f"{column} = ?" for column in filters]
            query += " WHERE " + " AND ".join(clauses)
            params.extend(filters.values())
        if order_by:
            query += f" ORDER BY {order_by}"
        with self._db:
            rows = self._db.execute(query, params).fetchall()
        return self._rows_to_dicts(rows)

    def create(self, **values) -> dict:
        """Insert a record and return it as a dict."""
        columns = ", ".join(values.keys())
        placeholders = ", ".join("?" for _ in values)
        with self._db:
            cursor = self._db.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                list(values.values()),
            )
            record_id = cursor.lastrowid
        return self.get_by_id(record_id)

    def update(self, record_id: int, **values) -> dict | None:
        """Update a record by id and return the updated record (or None)."""
        if not values:
            return self.get_by_id(record_id)
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._db:
            self._db.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                list(values.values()) + [record_id],
            )
        return self.get_by_id(record_id)

    def delete(self, record_id: int) -> None:
        """Delete a record by id."""
        with self._db:
            self._db.execute(
                f"DELETE FROM {self.table} WHERE id = ?", (record_id,)
            )


class UserRepository(BaseRepository):
    """Repository for the users table."""

    @property
    def table(self) -> str:
        return "users"

    def create_user(self, username: str, password: str) -> dict:
        """Create a user and return a public dict (no password hash)."""
        password_hash = generate_password_hash(password)
        user = self.create(username=username, password_hash=password_hash)
        return {"id": user["id"], "username": user["username"]}

    def get_by_username(self, username: str) -> dict | None:
        """Fetch a single user by username."""
        users = self.get_many(username=username)
        return users[0] if users else None


class TaskRepository(BaseRepository):
    """Repository for the tasks table."""

    @property
    def table(self) -> str:
        return "tasks"

    def create_task(self, title: str, owner_id: int) -> dict:
        """Create a task with pending status and current timestamp."""
        now = datetime.utcnow().isoformat()
        return self.create(
            title=title, status="pending", created_at=now, owner_id=owner_id
        )

    def get_tasks_by_owner(self, owner_id: int) -> list[dict]:
        """Fetch all tasks for an owner, newest first."""
        return self.get_many(owner_id=owner_id, order_by="created_at DESC")

    def get_task(self, task_id: int, owner_id: int | None = None) -> dict | None:
        """Fetch a single task, optionally scoped to an owner."""
        if owner_id is None:
            return self.get_by_id(task_id)
        return self.get_by_id(task_id, owner_id=owner_id)

    def update_task(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        """Update a task owned by owner_id and return the updated record."""
        task = self.get_task(task_id, owner_id=owner_id)
        if task is None:
            return None
        values = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        if not values:
            return task
        return self.update(task_id, **values)
