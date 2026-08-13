import sqlite3
from abc import ABC, abstractmethod


class DuplicateRecordError(Exception):
    pass


def open_database(database):
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class BaseRepository(ABC):
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @property
    @abstractmethod
    def table_name(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def writable_fields(self):
        raise NotImplementedError

    def create(self, values):
        fields = self._validated_fields(values)
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields)
        try:
            with self.connection_factory() as connection:
                cursor = connection.execute(
                    f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                    tuple(values[field] for field in fields),
                )
                return cursor.lastrowid
        except sqlite3.IntegrityError as error:
            raise DuplicateRecordError from error

    def get(self, record_id):
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def list(self):
        with self.connection_factory() as connection:
            return connection.execute(f"SELECT * FROM {self.table_name}").fetchall()

    def update(self, record_id, values):
        fields = self._validated_fields(values)
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self.connection_factory() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*[values[field] for field in fields], record_id),
            )
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def delete(self, record_id):
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            return cursor.rowcount > 0

    def _validated_fields(self, values):
        fields = tuple(values)
        if not fields or any(field not in self.writable_fields for field in fields):
            raise ValueError("invalid repository fields")
        return fields


class UserRepository(BaseRepository):
    table_name = "users"
    writable_fields = frozenset({"username", "password_hash", "email"})

    def initialize_schema(self):
        with self.connection_factory() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(users)")
            }
            if "email" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
                connection.execute(
                    "UPDATE users SET email = username WHERE email IS NULL"
                )

    def get_by_username(self, username):
        with self.connection_factory() as connection:
            return connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()

    def exists(self, user_id):
        with self.connection_factory() as connection:
            return (
                connection.execute(
                    "SELECT id FROM users WHERE id = ?", (user_id,)
                ).fetchone()
                is not None
            )


class TaskRepository(BaseRepository):
    table_name = "tasks"
    writable_fields = frozenset({"title", "status", "created_at", "owner_id"})

    def initialize_schema(self):
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
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
            }
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
            )

    def get_for_owner(self, task_id, owner_id):
        with self.connection_factory() as connection:
            return connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def list_for_owner(self, owner_id):
        with self.connection_factory() as connection:
            return connection.execute(
                """
                SELECT * FROM tasks
                WHERE owner_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (owner_id,),
            ).fetchall()

    def update_for_owner(self, task_id, owner_id, values):
        fields = self._validated_fields(values)
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self.connection_factory() as connection:
            existing = connection.execute(
                """
                SELECT tasks.id, tasks.status, users.email
                FROM tasks JOIN users ON users.id = tasks.owner_id
                WHERE tasks.id = ? AND tasks.owner_id = ?
                """,
                (task_id, owner_id),
            ).fetchone()
            if existing is None:
                return None, None
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                (*[values[field] for field in fields], task_id, owner_id),
            )
            updated = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return existing, updated
