import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager


class DuplicateRecordError(Exception):
    pass


class BaseRepository(ABC):
    def __init__(self, database):
        self.database = database

    @property
    @abstractmethod
    def table_name(self):
        pass

    @property
    @abstractmethod
    def writable_fields(self):
        pass

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _as_dict(row):
        return dict(row) if row is not None else None

    def create(self, values):
        fields = self._validated_fields(values)
        placeholders = ", ".join("?" for _ in fields)
        columns = ", ".join(fields)
        with self.connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values[field] for field in fields),
            )
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._as_dict(row)

    def get_by_id(self, record_id):
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return self._as_dict(row)

    def update(self, record_id, values):
        fields = self._validated_fields(values)
        assignments = ", ".join(f"{field} = ?" for field in fields)
        parameters = [values[field] for field in fields]
        parameters.append(record_id)
        with self.connection() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?", parameters
            )
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
        return self._as_dict(row)

    def delete(self, record_id):
        with self.connection() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
        return cursor.rowcount > 0

    def _validated_fields(self, values):
        fields = tuple(values)
        if not fields or not set(fields).issubset(self.writable_fields):
            raise ValueError("invalid fields")
        return fields


class UserRepository(BaseRepository):
    table_name = "users"
    writable_fields = frozenset({"username", "password_hash"})

    def initialize(self):
        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )

    def register(self, username, password_hash):
        try:
            return self.create(
                {"username": username, "password_hash": password_hash}
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateRecordError from error

    def get_by_username(self, username):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return self._as_dict(row)


class TaskRepository(BaseRepository):
    table_name = "tasks"
    writable_fields = frozenset({"title", "status", "created_at", "owner_id"})

    def initialize(self, legacy_username, legacy_password_hash):
        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    owner_id INTEGER NOT NULL REFERENCES users(id)
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
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (legacy_username, legacy_password_hash),
                )
                connection.execute(
                    "UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL",
                    (cursor.lastrowid,),
                )

    def create_for_owner(self, title, created_at, owner_id):
        return self.create(
            {
                "title": title,
                "status": "pending",
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )

    def list_for_owner(self, owner_id):
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM tasks WHERE owner_id = ?
                   ORDER BY created_at DESC, id DESC""",
                (owner_id,),
            ).fetchall()
        return [self._as_dict(row) for row in rows]

    def get_for_owner(self, task_id, owner_id):
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return self._as_dict(row)

    def update_for_owner(self, task_id, owner_id, values):
        fields = self._validated_fields(values)
        assignments = ", ".join(f"{field} = ?" for field in fields)
        parameters = [values[field] for field in fields]
        parameters.extend((task_id, owner_id))
        with self.connection() as connection:
            existing = connection.execute(
                """SELECT tasks.status, users.username AS owner_email
                   FROM tasks JOIN users ON users.id = tasks.owner_id
                   WHERE tasks.id = ? AND tasks.owner_id = ?""",
                (task_id, owner_id),
            ).fetchone()
            if existing is None:
                return None, None
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                parameters,
            )
            task = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return self._as_dict(existing), self._as_dict(task)
