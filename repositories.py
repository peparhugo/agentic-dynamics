"""Repository implementations for SQLite-backed application data."""

from abc import ABC
import sqlite3
from collections.abc import Iterable, Mapping


class BaseRepository(ABC):
    """Provide common CRUD operations for a single database table."""

    table_name: str

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def create(self, values: Mapping[str, object]) -> int:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        cursor = self.connection.execute(
            f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )
        return cursor.lastrowid

    def get_by_id(self, record_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
        ).fetchone()

    def list(self) -> list[sqlite3.Row]:
        return self.connection.execute(f"SELECT * FROM {self.table_name}").fetchall()

    def update(self, record_id: int, values: Mapping[str, object]) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        self.connection.execute(
            f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
            (*values.values(), record_id),
        )

    def delete(self, record_id: int) -> None:
        self.connection.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))


class UserRepository(BaseRepository):
    table_name = "users"

    def create_user(self, username: str, password_hash: str) -> int:
        return self.create({"username": username, "password_hash": password_hash})

    def get_by_username(self, username: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create_task(self, title: str, created_at: str, owner_id: int) -> int:
        return self.create({"title": title, "created_at": created_at, "owner_id": owner_id})

    def list_for_owner(self, owner_id: int) -> Iterable[sqlite3.Row]:
        return self.connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()

    def get_for_owner(self, task_id: int, owner_id: int) -> sqlite3.Row | None:
        return self.connection.execute(
            """
            SELECT tasks.id, tasks.title, tasks.status, tasks.created_at, users.username AS owner_email
            FROM tasks JOIN users ON users.id = tasks.owner_id
            WHERE tasks.id = ? AND tasks.owner_id = ?
            """,
            (task_id, owner_id),
        ).fetchone()

    def update_for_owner(self, task_id: int, owner_id: int, values: Mapping[str, object]) -> None:
        assignments = ", ".join(f"{column} = ?" for column in values)
        self.connection.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
            (*values.values(), task_id, owner_id),
        )


def initialize_database(connection: sqlite3.Connection) -> None:
    """Create application tables and migrate task ownership for existing databases."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
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
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
    if "owner_id" not in columns:
        connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
