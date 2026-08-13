import sqlite3
from abc import ABC, abstractmethod


class DuplicateUserError(Exception):
    pass


class BaseRepository(ABC):
    @property
    @abstractmethod
    def table_name(self):
        pass

    def __init__(self, database):
        self.database = database

    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def create(self, **values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            return cursor.lastrowid

    def get_by_id(self, record_id):
        with self._connect() as connection:
            return connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()

    def list(self):
        with self._connect() as connection:
            return connection.execute(f"SELECT * FROM {self.table_name}").fetchall()

    def update(self, record_id, **values):
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                (*values.values(), record_id),
            )
        return self.get_by_id(record_id)

    def delete(self, record_id):
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            return cursor.rowcount > 0

    @classmethod
    def initialize_database(cls, database):
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
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
                        id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        created_at TEXT NOT NULL,
                        owner_id INTEGER REFERENCES users(id)
                    )
                    """
                )
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(tasks)")
                }
                if "owner_id" not in columns:
                    connection.execute(
                        "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                    )
        finally:
            connection.close()


class UserRepository(BaseRepository):
    table_name = "users"

    def create_user(self, username, password_hash):
        try:
            return self.create(username=username, password_hash=password_hash)
        except sqlite3.IntegrityError as exc:
            raise DuplicateUserError from exc

    def get_by_username(self, username):
        with self._connect() as connection:
            return connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create_for_owner(self, title, created_at, owner_id):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM tasks"
            ).fetchone()
            task_id = row["next_id"]
            connection.execute(
                "INSERT INTO tasks (id, title, status, created_at, owner_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (task_id, title, "pending", created_at, owner_id),
            )
            connection.commit()
            return task_id
        finally:
            connection.close()

    def list_for_owner(self, owner_id):
        with self._connect() as connection:
            return connection.execute(
                "SELECT id, title, status, created_at FROM tasks "
                "WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
                (owner_id,),
            ).fetchall()

    def get_for_owner(self, task_id, owner_id):
        with self._connect() as connection:
            return connection.execute(
                "SELECT id, title, status, created_at FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()

    def update_for_owner(self, task_id, owner_id, **values):
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT tasks.id, tasks.title, tasks.status, "
                "users.username AS owner_email "
                "FROM tasks JOIN users ON users.id = tasks.owner_id "
                "WHERE tasks.id = ? AND tasks.owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            if existing is None:
                return None, None

            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                (*values.values(), task_id, owner_id),
            )
            updated = connection.execute(
                "SELECT id, title, status, created_at FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return existing, updated
