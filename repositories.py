"""Repositories for the todo application's persistent data."""

from abc import ABC, abstractmethod
from datetime import datetime
import sqlite3


def get_connection(database):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    return connection


class BaseRepository(ABC):
    """Small SQLite repository base with shared CRUD primitives."""

    table: str

    def __init__(self, database: str):
        self.database = database

    def _connect(self):
        return get_connection(self.database)

    def _execute(self, query, parameters=()):
        with self._connect() as connection:
            return connection.execute(query, parameters).fetchall()

    def get_by_id(self, record_id):
        rows = self._execute(f"SELECT * FROM {self.table} WHERE id = ?", (record_id,))
        return rows[0] if rows else None

    def list(self):
        return self._execute(f"SELECT * FROM {self.table}")

    def delete(self, record_id):
        with self._connect() as connection:
            cursor = connection.execute(f"DELETE FROM {self.table} WHERE id = ?", (record_id,))
            return cursor.rowcount > 0

    @abstractmethod
    def create(self, values):
        """Create one record and return its database representation."""

    @abstractmethod
    def update(self, record_id, values):
        """Update one record and return its database representation."""


class UserRepository(BaseRepository):
    table = "users"

    def create(self, values):
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (values["username"], values["password_hash"]),
            )
            return {"id": cursor.lastrowid, "username": values["username"]}

    def update(self, record_id, values):
        if not values:
            return self.get_by_id(record_id)
        assignments = ", ".join(f"{key} = ?" for key in values)
        parameters = [*values.values(), record_id]
        with self._connect() as connection:
            connection.execute(f"UPDATE users SET {assignments} WHERE id = ?", parameters)
        return self.get_by_id(record_id)

    def find_by_username(self, username):
        rows = self._execute("SELECT * FROM users WHERE username = ?", (username,))
        return rows[0] if rows else None

    def find_public_by_id(self, user_id):
        rows = self._execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        return rows[0] if rows else None


class TaskRepository(BaseRepository):
    table = "tasks"

    def create(self, values):
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
                (values["title"], values["created_at"], values["owner_id"]),
            )
            return {
                "id": cursor.lastrowid,
                "title": values["title"],
                "status": "pending",
                "created_at": values["created_at"],
            }

    def update(self, record_id, values):
        if values:
            assignments = ", ".join(f"{key} = ?" for key in values)
            parameters = [*values.values(), record_id]
            with self._connect() as connection:
                connection.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", parameters)
        return self.get_by_id(record_id)

    def create_for_owner(self, title, owner_id):
        return self.create({
            "title": title,
            "created_at": datetime.utcnow().isoformat(),
            "owner_id": owner_id,
        })

    def list_for_owner(self, owner_id):
        rows = self._execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )
        return [dict(row) for row in rows]

    def list_for_owner_paginated(self, owner_id, cursor=None, limit=20):
        conditions = ["owner_id = ?"]
        parameters = [owner_id]
        if cursor is not None:
            conditions.append("id < ?")
            parameters.append(cursor)
        parameters.append(limit + 1)
        rows = self._execute(
            "SELECT id, title, status, created_at FROM tasks "
            f"WHERE {' AND '.join(conditions)} ORDER BY id DESC LIMIT ?",
            parameters,
        )
        has_next = len(rows) > limit
        items = [dict(row) for row in rows[:limit]]
        total = self._execute(
            "SELECT COUNT(*) AS total FROM tasks WHERE owner_id = ?", (owner_id,)
        )[0]["total"]
        return {
            "data": items,
            "next_cursor": str(items[-1]["id"]) if has_next else None,
            "total": total,
        }

    def get_for_owner(self, task_id, owner_id):
        rows = self._execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )
        return dict(rows[0]) if rows else None

    def update_for_owner(self, task_id, owner_id, values):
        task = self.get_for_owner(task_id, owner_id)
        if task is None:
            return None
        if values:
            assignments = ", ".join(f"{key} = ?" for key in values)
            parameters = [*values.values(), task_id, owner_id]
            with self._connect() as connection:
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    parameters,
                )
        return self.get_for_owner(task_id, owner_id)


def initialize_database(database):
    """Create the schema and migrate databases created by older app versions."""
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'completed')),"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()[0]
        if "'completed'" not in schema:
            connection.execute("DROP INDEX IF EXISTS idx_tasks_owner_id")
            connection.execute("ALTER TABLE tasks RENAME TO tasks_old")
            connection.execute(
                "CREATE TABLE tasks ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  title TEXT NOT NULL,"
                "  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'completed')),"
                "  created_at TEXT NOT NULL,"
                "  owner_id INTEGER REFERENCES users(id)"
                ")"
            )
            connection.execute(
                "INSERT INTO tasks (id, title, status, created_at, owner_id) "
                "SELECT id, title, status, created_at, owner_id FROM tasks_old"
            )
            connection.execute("DROP TABLE tasks_old")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)")
