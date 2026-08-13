import sqlite3
from abc import ABC, abstractmethod


class DuplicateUserError(Exception):
    pass


class BaseRepository(ABC):
    def __init__(self, connection_factory):
        self.connection_factory = connection_factory

    @property
    @abstractmethod
    def table_name(self):
        raise NotImplementedError

    def create(self, values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self.connection_factory() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            return cursor.lastrowid

    def get(self, record_id):
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def update(self, record_id, values):
        if not values:
            return self.get(record_id)
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self.connection_factory() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*values.values(), record_id),
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


class UserRepository(BaseRepository):
    table_name = "users"

    def initialize(self):
        with self.connection_factory() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "email" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
                connection.execute(
                    "UPDATE users SET email = username WHERE email IS NULL"
                )

    def create_user(self, username, email, password_hash):
        try:
            return self.create(
                {
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                }
            )
        except sqlite3.IntegrityError as error:
            raise DuplicateUserError from error

    def find_by_username(self, username):
        with self.connection_factory() as connection:
            return connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()

    def find_identity(self, user_id):
        with self.connection_factory() as connection:
            return connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()


class TaskRepository(BaseRepository):
    table_name = "tasks"
    response_columns = "id, title, status, created_at"

    def initialize(self):
        with self.connection_factory() as connection:
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
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "owner_id" not in columns:
                connection.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
            )

    def create_task(self, title, status, created_at, owner_id):
        return self.create(
            {
                "title": title,
                "status": status,
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )

    def list_for_owner(self, owner_id, cursor, limit):
        with self.connection_factory() as connection:
            rows = connection.execute(
                f"SELECT {self.response_columns} FROM tasks WHERE owner_id = ? "
                "AND (? IS NULL OR id < ?) ORDER BY id DESC LIMIT ?",
                (owner_id, cursor, cursor, limit + 1),
            ).fetchall()
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            return rows, total

    def get_for_owner(self, task_id, owner_id):
        with self.connection_factory() as connection:
            return connection.execute(
                f"SELECT {self.response_columns} FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def update_for_owner(self, task_id, owner_id, values):
        with self.connection_factory() as connection:
            existing = connection.execute(
                "SELECT tasks.id, tasks.status, users.email, users.username "
                "FROM tasks JOIN users ON users.id = tasks.owner_id "
                "WHERE tasks.id = ? AND tasks.owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            if existing is None:
                return None, None
            if values:
                assignments = ", ".join(f"{column} = ?" for column in values)
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ?",
                    (*values.values(), task_id),
                )
            task = connection.execute(
                f"SELECT {self.response_columns} FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return existing, task
