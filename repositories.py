"""Repository implementations for the task management database."""

from abc import ABC, abstractmethod
import sqlite3


class UsernameAlreadyExistsError(Exception):
    """Raised when a user cannot be created because its username is taken."""


class BaseRepository(ABC):
    """Provide shared SQLite CRUD operations for concrete repositories."""

    table = ""
    columns = ()

    def __init__(self, database):
        self.database = database

    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, values):
        fields = [field for field in values if field in self.columns]
        placeholders = ", ".join("?" for _ in fields)
        with self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table} ({', '.join(fields)}) "
                f"VALUES ({placeholders})",
                tuple(values[field] for field in fields),
            )
            return cursor.lastrowid

    def get(self, record_id):
        with self._connect() as connection:
            return connection.execute(
                f"SELECT {', '.join(self.columns)} FROM {self.table} WHERE id = ?",
                (record_id,),
            ).fetchone()

    def list(self):
        with self._connect() as connection:
            return connection.execute(
                f"SELECT {', '.join(self.columns)} FROM {self.table}"
            ).fetchall()

    def update(self, record_id, values):
        fields = [field for field in values if field in self.columns and field != "id"]
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                tuple(values[field] for field in fields) + (record_id,),
            )
        return self.get(record_id)

    def delete(self, record_id):
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table} WHERE id = ?", (record_id,)
            )
        return cursor.rowcount > 0

    @abstractmethod
    def schema(self):
        """Create the repository's tables."""


class UserRepository(BaseRepository):
    table = "users"
    columns = ("id", "username", "password_hash")

    def schema(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )

    def create(self, values):
        try:
            return super().create(values)
        except sqlite3.IntegrityError as error:
            raise UsernameAlreadyExistsError from error

    def find_by_username(self, username):
        with self._connect() as connection:
            return connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()


class TaskRepository(BaseRepository):
    table = "tasks"
    columns = ("id", "title", "status", "created_at", "owner_id")

    def schema(self):
        with self._connect() as connection:
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
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )

    def find_for_owner(self, task_id, owner_id):
        with self._connect() as connection:
            return connection.execute(
                f"SELECT {', '.join(self.columns)} FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def list_for_owner(self, owner_id, cursor=None, limit=20):
        with self._connect() as connection:
            where = "WHERE owner_id = ?"
            parameters = [owner_id]
            if cursor is not None:
                where += " AND id < ?"
                parameters.append(cursor)
            rows = connection.execute(
                f"SELECT {', '.join(self.columns)} FROM tasks {where} "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                tuple(parameters) + (limit + 1,),
            ).fetchall()
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
        return rows, total

    def update_for_owner(self, task_id, owner_id, values):
        fields = [field for field in values if field in ("title", "status")]
        assignments = ", ".join(f"{field} = ?" for field in fields)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} "
                "WHERE id = ? AND owner_id = ?",
                tuple(values[field] for field in fields) + (task_id, owner_id),
            )
            return connection.execute(
                f"SELECT {', '.join(self.columns)} FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()


def init_database(database):
    """Create all repository schemas and apply the task-table migration."""
    UserRepository(database).schema()
    TaskRepository(database).schema()
