"""Database repositories for the task API."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
import sqlite3


class DuplicateUsernameError(Exception):
    """Raised when a user is registered with an existing username."""


class BaseRepository(ABC):
    """Common SQLite connection handling and CRUD operations."""

    columns = ()

    def __init__(self, database):
        self.database = database

    @property
    @abstractmethod
    def table(self):
        """Return the table managed by this repository."""

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, values):
        names = list(values)
        placeholders = ", ".join("?" for _ in names)
        query = f"INSERT INTO {self.table} ({', '.join(names)}) VALUES ({placeholders})"
        with self.connection() as connection:
            cursor = connection.execute(query, [values[name] for name in names])
            return cursor.lastrowid

    def get(self, record_id, columns=None):
        selected = ", ".join(columns or self.columns)
        with self.connection() as connection:
            return connection.execute(
                f"SELECT {selected} FROM {self.table} WHERE id = ?", (record_id,)
            ).fetchone()

    def list(self, where="", parameters=(), order_by=""):
        selected = ", ".join(self.columns)
        query = f"SELECT {selected} FROM {self.table}"
        if where:
            query += f" WHERE {where}"
        if order_by:
            query += f" ORDER BY {order_by}"
        with self.connection() as connection:
            return connection.execute(query, parameters).fetchall()

    def update(self, record_id, values, where="", parameters=()):
        assignments = ", ".join(f"{name} = ?" for name in values)
        query = f"UPDATE {self.table} SET {assignments} WHERE id = ?"
        query_parameters = [values[name] for name in values] + [record_id]
        if where:
            query += f" AND {where}"
            query_parameters.extend(parameters)
        with self.connection() as connection:
            return connection.execute(query, query_parameters).rowcount

    def delete(self, record_id):
        with self.connection() as connection:
            return connection.execute(
                f"DELETE FROM {self.table} WHERE id = ?", (record_id,)
            ).rowcount

    @staticmethod
    def initialize_database(database):
        """Create or migrate the schema without discarding existing task rows."""
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT,
                    password_hash TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
                """
            )
            task_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
            }
            if "owner_id" not in task_columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            user_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(users)")
            }
            if "email" not in user_columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")


class UserRepository(BaseRepository):
    columns = ("id", "username", "email", "password_hash")

    @property
    def table(self):
        return "users"

    def create_user(self, username, email, password_hash):
        try:
            return self.create(
                {"username": username, "email": email, "password_hash": password_hash}
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateUsernameError from exc

    def find_by_id(self, user_id):
        return self.get(user_id, ("id", "username", "email"))

    def find_by_username(self, username):
        with self.connection() as connection:
            return connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()


class TaskRepository(BaseRepository):
    columns = ("id", "title", "status", "created_at")

    @property
    def table(self):
        return "tasks"

    def create_task(self, title, created_at, owner_id):
        task_id = self.create(
            {"title": title, "created_at": created_at, "owner_id": owner_id}
        )
        return self.get(task_id)

    def find_for_owner(self, task_id, owner_id):
        rows = self.list("id = ? AND owner_id = ?", (task_id, owner_id))
        return rows[0] if rows else None

    def list_for_owner(self, owner_id):
        return self.list(
            "owner_id = ?", (owner_id,), "created_at DESC, id DESC"
        )

    def update_for_owner(self, task_id, owner_id, values):
        changed = self.update(task_id, values, "owner_id = ?", (owner_id,))
        if not changed:
            return None
        return self.get(task_id)
