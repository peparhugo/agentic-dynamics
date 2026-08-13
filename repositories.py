import sqlite3
from abc import ABC, abstractmethod


class DuplicateUsernameError(Exception):
    pass


class BaseRepository(ABC):
    @property
    @abstractmethod
    def table_name(self):
        raise NotImplementedError

    @property
    @abstractmethod
    def columns(self):
        raise NotImplementedError

    def __init__(self, database):
        self.database = database

    @staticmethod
    def connect(database):
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @classmethod
    def initialize_database(cls, database):
        with cls.connect(database) as connection:
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
                    created_at TEXT NOT NULL,
                    owner_id INTEGER REFERENCES users(id)
                )
                """
            )

            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
            }
            if "owner_id" not in columns:
                # Nullable ownership preserves legacy rows without exposing them to users.
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
            )

    def create(self, **values):
        self._validate_fields(values)
        fields = list(values)
        placeholders = ", ".join("?" for _ in fields)
        with self.connect(self.database) as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({', '.join(fields)}) "
                f"VALUES ({placeholders})",
                [values[field] for field in fields],
            )
            record_id = cursor.lastrowid
        return self.get_by_id(record_id)

    def get_by_id(self, record_id):
        with self.connect(self.database) as connection:
            row = connection.execute(
                f"SELECT {', '.join(self.columns)} FROM {self.table_name} WHERE id = ?",
                (record_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def update(self, record_id, **values):
        self._validate_fields(values)
        if values:
            fields = list(values)
            assignments = ", ".join(f"{field} = ?" for field in fields)
            parameters = [values[field] for field in fields] + [record_id]
            with self.connect(self.database) as connection:
                connection.execute(
                    f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                    parameters,
                )
        return self.get_by_id(record_id)

    def delete(self, record_id):
        with self.connect(self.database) as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
        return cursor.rowcount > 0

    def _validate_fields(self, values):
        invalid_fields = set(values) - set(self.columns)
        if invalid_fields or "id" in values:
            raise ValueError("invalid repository fields")


class TaskRepository(BaseRepository):
    table_name = "tasks"
    columns = ("id", "title", "status", "created_at", "owner_id")
    public_columns = ("id", "title", "status", "created_at")

    def create_for_owner(self, title, created_at, owner_id):
        task = self.create(title=title, created_at=created_at, owner_id=owner_id)
        return self.get_for_owner(task["id"], owner_id)

    def list_for_owner(self, owner_id, cursor=None, limit=20):
        cursor_clause = " AND id < ?" if cursor is not None else ""
        parameters = [owner_id]
        if cursor is not None:
            parameters.append(cursor)
        parameters.append(limit + 1)
        with self.connect(self.database) as connection:
            rows = connection.execute(
                f"SELECT {', '.join(self.public_columns)} FROM tasks "
                f"WHERE owner_id = ?{cursor_clause} ORDER BY id DESC LIMIT ?",
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def count_for_owner(self, owner_id):
        with self.connect(self.database) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()
        return row["total"]

    def get_for_owner(self, task_id, owner_id):
        with self.connect(self.database) as connection:
            row = connection.execute(
                f"SELECT {', '.join(self.public_columns)} FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def update_for_owner(self, task_id, owner_id, **values):
        if self.get_for_owner(task_id, owner_id) is None:
            return None

        self._validate_fields(values)
        if values:
            fields = list(values)
            assignments = ", ".join(f"{field} = ?" for field in fields)
            parameters = [values[field] for field in fields] + [task_id, owner_id]
            with self.connect(self.database) as connection:
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    parameters,
                )
        return self.get_for_owner(task_id, owner_id)


class UserRepository(BaseRepository):
    table_name = "users"
    columns = ("id", "username", "password_hash")

    def create_user(self, username, password_hash):
        try:
            return self.create(username=username, password_hash=password_hash)
        except sqlite3.IntegrityError as error:
            raise DuplicateUsernameError from error

    def get_by_username(self, username):
        with self.connect(self.database) as connection:
            row = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        return dict(row) if row is not None else None
