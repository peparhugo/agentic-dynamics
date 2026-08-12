"""Repositories for persistence used by the task API."""

from abc import ABC, abstractmethod
from contextlib import closing
import secrets
import sqlite3

from werkzeug.security import generate_password_hash


class DuplicateUserError(Exception):
    """Raised when a username is already registered."""


class BaseRepository(ABC):
    """Shared SQLite CRUD helpers for concrete repositories."""

    table = None

    def __init__(self, database):
        self.database = database

    def _connection(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _insert(self, fields):
        columns = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        with self._connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table} ({columns}) VALUES ({placeholders})",
                tuple(fields.values()),
            )
            return cursor.lastrowid

    def _get(self, where, values, columns="*"):
        with closing(self._connection()) as connection:
            return connection.execute(
                f"SELECT {columns} FROM {self.table} WHERE {where}", values
            ).fetchone()

    def _list(self, where=None, values=(), columns="*", order_by=None):
        query = f"SELECT {columns} FROM {self.table}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        with closing(self._connection()) as connection:
            return connection.execute(query, values).fetchall()

    def _count(self, where=None, values=()):
        query = f"SELECT COUNT(*) FROM {self.table}"
        if where:
            query += f" WHERE {where}"
        with closing(self._connection()) as connection:
            return connection.execute(query, values).fetchone()[0]

    def _update(self, changes, where, values):
        assignments = ", ".join(f"{column} = ?" for column in changes)
        with self._connection() as connection:
            connection.execute(
                f"UPDATE {self.table} SET {assignments} WHERE {where}",
                tuple(changes.values()) + tuple(values),
            )

    def _delete(self, where, values):
        with self._connection() as connection:
            connection.execute(f"DELETE FROM {self.table} WHERE {where}", values)

    @abstractmethod
    def create(self, **fields):
        """Create a record."""

    @abstractmethod
    def get(self, record_id):
        """Get a record by ID."""

    @abstractmethod
    def list(self):
        """List records."""

    @abstractmethod
    def update(self, record_id, **fields):
        """Update a record."""

    @abstractmethod
    def delete(self, record_id):
        """Delete a record."""


class UserRepository(BaseRepository):
    table = "users"

    def create(self, username, password):
        try:
            return self._insert(
                {"username": username, "password_hash": generate_password_hash(password)}
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateUserError from error

    def get(self, record_id):
        return self._get("id = ?", (record_id,), "id, username")

    def get_by_username(self, username):
        return self._get(
            "username = ?", (username,), "id, username, password_hash"
        )

    def list(self):
        return self._list()

    def update(self, record_id, **fields):
        self._update(fields, "id = ?", (record_id,))

    def delete(self, record_id):
        self._delete("id = ?", (record_id,))


class TaskRepository(BaseRepository):
    table = "tasks"
    columns = "id, title, status, created_at"

    def create(self, title, status, created_at, owner_id):
        task_id = self._insert(
            {"title": title, "status": status, "created_at": created_at, "owner_id": owner_id}
        )
        return self.get_for_owner(task_id, owner_id)

    def get(self, record_id):
        return self._get("id = ?", (record_id,), self.columns)

    def get_for_owner(self, record_id, owner_id):
        return self._get("id = ? AND owner_id = ?", (record_id, owner_id), self.columns)

    def list(self):
        return self._list(order_by="created_at DESC, id DESC")

    def list_for_owner(self, owner_id):
        return self._list(
            "owner_id = ?", (owner_id,), self.columns, "created_at DESC, id DESC"
        )

    def page_for_owner(self, owner_id, cursor=None, limit=20):
        where = "owner_id = ?"
        values = [owner_id]
        if cursor is not None:
            where += " AND id < ?"
            values.append(cursor)
        rows = self._list(
            where,
            tuple(values),
            self.columns,
            "created_at DESC, id DESC",
        )
        return rows[:limit + 1], self._count("owner_id = ?", (owner_id,))

    def update(self, record_id, **fields):
        self._update(fields, "id = ?", (record_id,))

    def update_for_owner(self, record_id, owner_id, **fields):
        self._update(fields, "id = ? AND owner_id = ?", (record_id, owner_id))
        return self.get_for_owner(record_id, owner_id)

    def delete(self, record_id):
        self._delete("id = ?", (record_id,))


def initialize_database(database):
    """Create the schema and migrate databases made by older API versions."""
    users = UserRepository(database)
    tasks = TaskRepository(database)
    with users._connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, owner_id INTEGER REFERENCES users(id))"
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)").fetchall()}
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        if connection.execute("SELECT 1 FROM tasks WHERE owner_id IS NULL").fetchone():
            legacy = connection.execute(
                "SELECT id FROM users WHERE username LIKE 'legacy%' ORDER BY id LIMIT 1"
            ).fetchone()
            if legacy:
                legacy_id = legacy["id"]
            else:
                username = "legacy"
                suffix = 0
                while connection.execute(
                    "SELECT 1 FROM users WHERE username = ?", (username,)
                ).fetchone():
                    suffix += 1
                    username = f"legacy_{suffix}"
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(secrets.token_urlsafe(32))),
                )
                legacy_id = cursor.lastrowid
            connection.execute("UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL", (legacy_id,))
