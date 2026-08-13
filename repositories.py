"""Repository classes for SQLite-backed application data."""

from abc import ABC, abstractmethod
import sqlite3
from typing import Any, Callable


class BaseRepository(ABC):
    """Provide common CRUD operations for a database table."""

    table_name: str

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        self.connection_factory = connection_factory

    @classmethod
    def initialize_schema(cls, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        """Create and migrate the application schema."""
        with connection_factory() as conn:
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
            task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
            user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            if "email" not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

    @abstractmethod
    def _columns(self) -> tuple[str, ...]:
        """Return the public columns selected by the common read methods."""

    def create(self, **values: Any) -> int:
        columns = tuple(values)
        placeholders = ", ".join("?" for _ in columns)
        with self.connection_factory() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            return cursor.lastrowid

    def get_by_id(self, record_id: int) -> sqlite3.Row | None:
        with self.connection_factory() as conn:
            return conn.execute(
                f"SELECT {', '.join(self._columns())} FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def list_all(self) -> list[sqlite3.Row]:
        with self.connection_factory() as conn:
            return conn.execute(f"SELECT {', '.join(self._columns())} FROM {self.table_name}").fetchall()

    def update(self, record_id: int, **values: Any) -> None:
        if not values:
            return
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                tuple(values.values()) + (record_id,),
            )

    def delete(self, record_id: int) -> None:
        with self.connection_factory() as conn:
            conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))


class TaskRepository(BaseRepository):
    """Persist and retrieve tasks belonging to users."""

    table_name = "tasks"

    def _columns(self) -> tuple[str, ...]:
        return ("id", "title", "status", "created_at")

    def list_for_owner(self, owner_id: int) -> list[sqlite3.Row]:
        with self.connection_factory() as conn:
            return conn.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchall()

    def list_page_for_owner(
        self, owner_id: int, cursor: int | None, limit: int
    ) -> tuple[list[sqlite3.Row], int]:
        """Return one newest-first task page and the owner's total task count."""
        with self.connection_factory() as conn:
            total = conn.execute("SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)).fetchone()[0]
            if cursor is None:
                rows = conn.execute(
                    """
                    SELECT id, title, status, created_at FROM tasks
                    WHERE owner_id = ? ORDER BY id DESC LIMIT ?
                    """,
                    (owner_id, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, title, status, created_at FROM tasks
                    WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?
                    """,
                    (owner_id, cursor, limit + 1),
                ).fetchall()
            return rows, total

    def find_for_owner(self, task_id: int, owner_id: int) -> sqlite3.Row | None:
        with self.connection_factory() as conn:
            return conn.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def find_for_owner_with_email(self, task_id: int, owner_id: int) -> sqlite3.Row | None:
        with self.connection_factory() as conn:
            return conn.execute(
                """
                SELECT tasks.id, tasks.status, tasks.title, users.email
                FROM tasks JOIN users ON users.id = tasks.owner_id
                WHERE tasks.id = ? AND tasks.owner_id = ?
                """,
                (task_id, owner_id),
            ).fetchone()

    def update_for_owner(self, task_id: int, owner_id: int, **values: Any) -> None:
        if not values:
            return
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as conn:
            conn.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                tuple(values.values()) + (task_id, owner_id),
            )


class UserRepository(BaseRepository):
    """Persist and retrieve user accounts."""

    table_name = "users"

    def _columns(self) -> tuple[str, ...]:
        return ("id", "username", "email", "password_hash")

    def create_user(self, username: str, email: str, password_hash: str) -> int | None:
        try:
            return self.create(username=username, email=email, password_hash=password_hash)
        except sqlite3.IntegrityError:
            return None

    def find_by_username(self, username: str) -> sqlite3.Row | None:
        with self.connection_factory() as conn:
            return conn.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()

    def exists(self, user_id: int) -> bool:
        return self.get_by_id(user_id) is not None
