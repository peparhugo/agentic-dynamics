"""Repository layer: all SQLite access for the task management API lives here.

Route handlers in taskapp.py talk to these repositories instead of touching
sqlite3 directly.
"""

import sqlite3
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseRepository(ABC):
    """Shared SQLite CRUD plumbing for concrete repositories."""

    def __init__(self, database: str):
        self.database = database

    @property
    @abstractmethod
    def table_name(self) -> str:
        ...

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        return conn

    def get_by_id(self, record_id: int) -> Optional[sqlite3.Row]:
        conn = self._connect()
        try:
            return conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        finally:
            conn.close()

    def delete(self, record_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,))
            conn.commit()
        finally:
            conn.close()

    def list_all(self) -> list:
        conn = self._connect()
        try:
            return conn.execute(f"SELECT * FROM {self.table_name}").fetchall()
        finally:
            conn.close()


class UserRepository(BaseRepository):
    table_name = "users"

    def create_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Migration: pre-existing databases created before email was added
        # won't have the column yet, so add it without touching existing rows.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")

    def get_by_username(self, username: str) -> Optional[sqlite3.Row]:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            conn.close()

    def create(self, username: str, password_hash: str, email: str) -> int:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create_table(self, conn: sqlite3.Connection) -> None:
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
        # Migration: pre-existing databases created before owner_id was added
        # won't have the column yet, so add it without touching existing rows.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")

    def create(self, title: str, status: str, created_at: str, owner_id: int) -> sqlite3.Row:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
                (title, status, created_at, owner_id),
            )
            conn.commit()
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        finally:
            conn.close()

    def list_for_owner(self, owner_id: int) -> list:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()
        finally:
            conn.close()

    def get_for_owner(self, task_id: int, owner_id: int) -> Optional[sqlite3.Row]:
        conn = self._connect()
        try:
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
            ).fetchone()
        finally:
            conn.close()

    def update(self, task_id: int, title: str, status: str) -> Optional[sqlite3.Row]:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id),
            )
            conn.commit()
            return conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        finally:
            conn.close()


def init_db(database: str) -> None:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    try:
        UserRepository(database).create_table(conn)
        TaskRepository(database).create_table(conn)
        conn.commit()
    finally:
        conn.close()
