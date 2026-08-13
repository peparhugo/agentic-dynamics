"""Repository classes that isolate SQLite access from the web layer."""

import sqlite3
from abc import ABC, abstractmethod


class BaseRepository(ABC):
    """Provide common CRUD primitives for a single SQLite table."""

    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @property
    @abstractmethod
    def table_name(self):
        """Return the table managed by this repository."""

    def create(self, values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
        return cursor.lastrowid

    def get_by_id(self, record_id):
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def update(self, record_id, values):
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                tuple(values.values()) + (record_id,),
            )
        return cursor.rowcount

    def delete(self, record_id):
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
        return cursor.rowcount


class UserRepository(BaseRepository):
    @property
    def table_name(self):
        return "users"

    def initialize(self):
        with self.connection_factory() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    email TEXT
                )
                """
            )
            columns = {column["name"] for column in connection.execute("PRAGMA table_info(users)")}
            if "email" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")

    def create_user(self, username, password_hash, email):
        try:
            return self.create(
                {"username": username, "password_hash": password_hash, "email": email}
            )
        except sqlite3.IntegrityError:
            return None

    def find_by_username(self, username):
        with self.connection_factory() as connection:
            return connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()


class TaskRepository(BaseRepository):
    @property
    def table_name(self):
        return "tasks"

    def initialize(self):
        with self.connection_factory() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    owner_id INTEGER
                )
                """
            )
            columns = {column["name"] for column in connection.execute("PRAGMA table_info(tasks)")}
            # Existing task rows remain intact; new tasks always receive an owner.
            if "owner_id" not in columns:
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            connection.execute("CREATE INDEX IF NOT EXISTS tasks_owner_id_idx ON tasks(owner_id)")

    def create_for_owner(self, title, created_at, owner_id):
        task_id = self.create(
            {"title": title, "created_at": created_at, "owner_id": owner_id}
        )
        return self.find_by_id_and_owner(task_id, owner_id)

    def find_by_id_and_owner(self, task_id, owner_id):
        with self.connection_factory() as connection:
            return connection.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def list_page_for_owner(self, owner_id, cursor, limit):
        with self.connection_factory() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            query = (
                "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? "
            )
            parameters = [owner_id]
            if cursor is not None:
                query += "AND id < ? "
                parameters.append(cursor)
            rows = connection.execute(
                query + "ORDER BY id DESC LIMIT ?", parameters + [limit + 1]
            ).fetchall()
        has_next_page = len(rows) > limit
        tasks = rows[:limit]
        next_cursor = tasks[-1]["id"] if has_next_page else None
        return tasks, next_cursor, total

    def update_for_owner(self, task_id, owner_id, values):
        """Update a task and return its former status, owner email, and new row."""
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as connection:
            existing_task = connection.execute(
                "SELECT tasks.status, users.email FROM tasks "
                "JOIN users ON users.id = tasks.owner_id "
                "WHERE tasks.id = ? AND tasks.owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            if existing_task is None:
                return None, None
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                tuple(values.values()) + (task_id, owner_id),
            )
            task = connection.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return existing_task, task
