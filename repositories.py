"""SQLite repositories for task API persistence."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
import sqlite3


class BaseRepository(ABC):
    """Provide common CRUD operations for a single SQLite table."""

    table_name: str

    def __init__(self, connection_factory: Callable[[], sqlite3.Connection]) -> None:
        self.connection_factory = connection_factory

    @property
    @abstractmethod
    def select_columns(self) -> str:
        """Return the columns exposed by this repository."""

    def create(self, **values: object) -> int:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            return cursor.lastrowid

    def get_by_id(self, record_id: int) -> sqlite3.Row | None:
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT {self.select_columns} FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def list_all(self) -> Sequence[sqlite3.Row]:
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT {self.select_columns} FROM {self.table_name}"
            ).fetchall()

    def update(self, record_id: int, **values: object) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*values.values(), record_id),
            )

    def delete(self, record_id: int) -> None:
        with self.connection_factory() as connection:
            connection.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))


class TaskRepository(BaseRepository):
    """Persist tasks and constrain task operations to their owner."""

    table_name = "tasks"
    select_columns = "id, title, status, created_at"

    def initialize(self) -> None:
        with self.connection_factory() as connection:
            connection.execute(
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
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")

    def create_for_owner(self, title: str, created_at: str, owner_id: int) -> int:
        return self.create(title=title, created_at=created_at, owner_id=owner_id)

    def get_for_owner(self, task_id: int, owner_id: int) -> sqlite3.Row | None:
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT {self.select_columns} FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def list_for_owner(self, owner_id: int) -> Sequence[sqlite3.Row]:
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT {self.select_columns} FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()

    def update_for_owner(self, task_id: int, owner_id: int, title: str, status: str) -> None:
        with self.connection_factory() as connection:
            connection.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
                (title, status, task_id, owner_id),
            )


class UserRepository(BaseRepository):
    """Persist user credentials and notification contact information."""

    table_name = "users"
    select_columns = "id, username, email, password_hash"

    def initialize(self) -> None:
        with self.connection_factory() as connection:
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
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
            if "email" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")

    def create_user(self, username: str, email: str | None, password_hash: str) -> int:
        return self.create(username=username, email=email, password_hash=password_hash)

    def get_by_username(self, username: str) -> sqlite3.Row | None:
        with self.connection_factory() as connection:
            return connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()

    def get_email(self, user_id: int) -> str | None:
        with self.connection_factory() as connection:
            user = connection.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
        return user["email"] if user is not None else None
