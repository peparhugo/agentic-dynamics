"""
Repository layer for the Todo API.

Encapsulates all SQLite access. Route handlers interact with repository
objects instead of issuing raw SQL.
"""

import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

import bcrypt

DEFAULT_DATABASE = os.environ.get("DATABASE", "todos.db")


def database_path() -> str:
    return os.environ.get("DATABASE", DEFAULT_DATABASE)


def get_db():
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
    migrate()


def migrate():
    with get_db() as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            conn.commit()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


class BaseRepository(ABC):
    """Abstract base class with common CRUD operations."""

    @property
    @abstractmethod
    def table_name(self) -> str:
        raise NotImplementedError

    def _get_db(self):
        return get_db()

    def _fetch_one(self, query: str, params=()):
        with self._get_db() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def _fetch_all(self, query: str, params=()):
        with self._get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def _execute(self, query: str, params=()):
        with self._get_db() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def get_by_id(self, record_id: int):
        return self._fetch_one(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
        )

    def create(self, data: dict):
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        record_id = self._execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(data.values()),
        )
        return self.get_by_id(record_id)

    def update(self, record_id: int, fields: dict):
        if not fields:
            return self.get_by_id(record_id)
        assignments = ", ".join(f"{column} = ?" for column in fields)
        params = tuple(fields.values()) + (record_id,)
        self._execute(
            f"UPDATE {self.table_name} SET {assignments} WHERE id = ?", params
        )
        return self.get_by_id(record_id)

    def delete(self, record_id: int):
        self._execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))

    def all(self):
        return self._fetch_all(f"SELECT * FROM {self.table_name}")


class UserRepository(BaseRepository):
    """Repository for the users table."""

    table_name = "users"

    def create_user(self, username: str, password: str) -> dict:
        password_hash = hash_password(password)
        record_id = self._execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        return {"id": record_id, "username": username}

    def get_by_username(self, username: str) -> dict | None:
        return self._fetch_one("SELECT * FROM users WHERE username = ?", (username,))


class TaskRepository(BaseRepository):
    """Repository for the tasks table."""

    table_name = "tasks"

    def create_task(self, owner_id: int, title: str) -> dict:
        now = datetime.utcnow().isoformat()
        record_id = self._execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, "pending", now, owner_id),
        )
        return {
            "id": record_id,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }

    def get_tasks(self, owner_id: int, limit: int = 20, cursor: int | None = None):
        where = "owner_id = ?"
        params = [owner_id]
        if cursor is not None:
            where += " AND id < ?"
            params.append(cursor)
        rows = self._fetch_all(
            f"SELECT * FROM tasks WHERE {where} ORDER BY id DESC LIMIT ?",
            params + [limit + 1],
        )
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = str(page[-1]["id"]) if has_more and page else None
        return page, next_cursor

    def count_tasks(self, owner_id: int) -> int:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()
            return int(row["n"])

    def get_task(self, task_id: int, owner_id: int) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )

    def update_task(
        self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None
    ) -> dict | None:
        if self.get_task(task_id, owner_id) is None:
            return None
        fields = {}
        if title is not None:
            fields["title"] = title
        if status is not None:
            fields["status"] = status
        if fields:
            self.update(task_id, fields)
        return self.get_task(task_id, owner_id)
