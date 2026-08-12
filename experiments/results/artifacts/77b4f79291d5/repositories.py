"""Repository implementations for the task application database."""

from abc import ABC, abstractmethod
import sqlite3


class DuplicateUserError(Exception):
    """Raised when a user username violates the unique constraint."""


class BaseRepository(ABC):
    """Provide common CRUD operations for SQLite-backed repositories."""

    table_name = None
    columns = frozenset()

    def __init__(self, database):
        self.database = database

    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, values):
        fields = self._allowed_fields(values)
        names = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        with self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({names}) VALUES ({placeholders})",
                tuple(values[field] for field in fields),
            )
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()

    def get(self, record_id):
        with self._connect() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def list(self, filters=None):
        filters = filters or {}
        fields = tuple(field for field in filters if field in self.columns)
        where = " AND ".join(f"{field} = ?" for field in fields)
        query = f"SELECT * FROM {self.table_name}"
        if where:
            query += f" WHERE {where}"
        with self._connect() as connection:
            return connection.execute(query, tuple(filters[field] for field in fields)).fetchall()

    def update(self, record_id, values):
        fields = self._allowed_fields(values)
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                tuple(values[field] for field in fields) + (record_id,),
            )
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def delete(self, record_id):
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            return cursor.rowcount > 0

    def _allowed_fields(self, values):
        fields = tuple(field for field in values if field in self.columns)
        if not fields:
            raise ValueError("at least one valid field is required")
        return fields

    @classmethod
    @abstractmethod
    def initialize_schema(cls, database):
        """Create or migrate the table managed by this repository."""


class UserRepository(BaseRepository):
    table_name = "users"
    columns = frozenset({"username", "password_hash"})

    @classmethod
    def initialize_schema(cls, database):
        with sqlite3.connect(database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )

    def find_by_username(self, username):
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()

    def create(self, values):
        try:
            return super().create(values)
        except sqlite3.IntegrityError as error:
            raise DuplicateUserError from error


class TaskRepository(BaseRepository):
    table_name = "tasks"
    columns = frozenset({"title", "status", "created_at", "owner_id"})

    @classmethod
    def initialize_schema(cls, database):
        with sqlite3.connect(database) as connection:
            connection.row_factory = sqlite3.Row
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
            task_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "owner_id" not in task_columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )

    def list_for_owner(self, owner_id, cursor=None, limit=20):
        with self._connect() as connection:
            parameters = [owner_id]
            cursor_filter = ""
            if cursor is not None:
                cursor_filter = """
                    AND (
                        created_at < (SELECT created_at FROM tasks WHERE id = ?)
                        OR (
                            created_at = (SELECT created_at FROM tasks WHERE id = ?)
                            AND id < ?
                        )
                    )
                """
                parameters.extend((cursor, cursor, cursor))
            parameters.append(limit)
            return connection.execute(
                f"""
                SELECT * FROM tasks
                WHERE owner_id = ?
                {cursor_filter}
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()

    def count_for_owner(self, owner_id):
        with self._connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]

    def get_for_owner(self, task_id, owner_id):
        with self._connect() as connection:
            return connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def update_for_owner(self, task_id, owner_id, values):
        fields = self._allowed_fields(values)
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                tuple(values[field] for field in fields) + (task_id, owner_id),
            )
            return connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
