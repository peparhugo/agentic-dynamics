"""SQLite repositories for task-management data."""

from abc import ABC, abstractmethod
import sqlite3


class DuplicateUserError(Exception):
    """Raised when a username already exists."""


class BaseRepository(ABC):
    """Common CRUD operations for a SQLite table."""

    @property
    @abstractmethod
    def table_name(self):
        """Return the table managed by this repository."""

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    def create(self, **values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.connection_factory() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
        return self.get(cursor.lastrowid)

    def get(self, identifier):
        with self.connection_factory() as conn:
            return conn.execute(f"SELECT * FROM {self.table_name} WHERE id = ?", (identifier,)).fetchone()

    def update(self, identifier, **values):
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*values.values(), identifier),
            )
        return self.get(identifier)

    def delete(self, identifier):
        with self.connection_factory() as conn:
            cursor = conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (identifier,))
        return cursor.rowcount > 0

    def list_all(self):
        with self.connection_factory() as conn:
            return conn.execute(f"SELECT * FROM {self.table_name}").fetchall()


class UserRepository(BaseRepository):
    @property
    def table_name(self):
        return "users"

    def initialize(self):
        with self.connection_factory() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT,
                    password_hash TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            if "email" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

    def create_user(self, username, email, password_hash):
        try:
            return self.create(username=username, email=email, password_hash=password_hash)
        except sqlite3.IntegrityError as error:
            raise DuplicateUserError from error

    def get_by_username(self, username):
        with self.connection_factory() as conn:
            return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


class TaskRepository(BaseRepository):
    @property
    def table_name(self):
        return "tasks"

    def initialize(self):
        with self.connection_factory() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    owner_id INTEGER REFERENCES users(id)
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")

    def create_task(self, title, created_at, owner_id):
        return self.create(title=title, created_at=created_at, owner_id=owner_id)

    def list_for_owner(self, owner_id):
        with self.connection_factory() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
            ).fetchall()

    def get_for_owner(self, identifier, owner_id):
        with self.connection_factory() as conn:
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (identifier, owner_id)
            ).fetchone()

    def update_for_owner(self, identifier, owner_id, title=None, status=None):
        task = self.get_for_owner(identifier, owner_id)
        if task is None:
            return None, None
        updated = self.update(
            identifier,
            title=title if title is not None else task["title"],
            status=status if status is not None else task["status"],
        )
        return task, updated
