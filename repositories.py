"""Database repositories for users and tasks."""

from abc import ABC, abstractmethod
import secrets
import sqlite3

from werkzeug.security import generate_password_hash


VALID_STATUSES = {"pending", "done", "completed"}


class UserAlreadyExistsError(Exception):
    """Raised when a username is already registered."""


class BaseRepository(ABC):
    """Common SQLite CRUD operations shared by concrete repositories."""

    def __init__(self, database):
        self.database = database

    @property
    @abstractmethod
    def table_name(self):
        """Return the table managed by this repository."""

    def _connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, values):
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        with self._connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                tuple(values.values()),
            )
            connection.commit()
            return cursor.lastrowid

    def get(self, record_id):
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def update(self, record_id, values):
        if not values:
            return self.get(record_id)
        assignments = ", ".join(f"{column} = ?" for column in values)
        with self._connect() as connection:
            connection.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?",
                tuple(values.values()) + (record_id,),
            )
            connection.commit()
        return self.get(record_id)

    def delete(self, record_id):
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            connection.commit()
            return cursor.rowcount > 0


class UserRepository(BaseRepository):
    @property
    def table_name(self):
        return "users"

    def create_user(self, username, password):
        try:
            user_id = self.create(
                {"username": username, "password_hash": generate_password_hash(password)}
            )
        except sqlite3.IntegrityError as exc:
            raise UserAlreadyExistsError from exc
        return {"id": user_id, "username": username}

    def find_by_username(self, username):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def find_by_id(self, user_id):
        return self.get(user_id)


class TaskRepository(BaseRepository):
    @property
    def table_name(self):
        return "tasks"

    def create_task(self, title, owner_id, created_at):
        task_id = self.create(
            {
                "title": title,
                "status": "pending",
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )
        return {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }

    def list_for_owner(self, owner_id, cursor=None, limit=20):
        with self._connect() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
            ).fetchone()[0]
            query = (
                "SELECT id, title, status, created_at FROM tasks "
                "WHERE owner_id = ?"
            )
            parameters = [owner_id]
            if cursor is not None:
                query += " AND id < ?"
                parameters.append(cursor)
            query += " ORDER BY id DESC LIMIT ?"
            parameters.append(limit + 1)
            rows = connection.execute(query, parameters).fetchall()
            return [dict(row) for row in rows], total

    def get_for_owner(self, task_id, owner_id):
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, title, status, created_at FROM tasks "
                "WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update_for_owner(self, task_id, owner_id, title=None, status=None):
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        if status is not None and status not in VALID_STATUSES:
            raise ValueError("status must be either 'pending', 'done', or 'completed'")
        values = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        if values:
            with self._connect() as connection:
                assignments = ", ".join(f"{column} = ?" for column in values)
                connection.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    tuple(values.values()) + (task_id, owner_id),
                )
                connection.commit()
        return self.get_for_owner(task_id, owner_id)


def initialize_database(database):
    """Create the schema and migrate databases created by older versions."""
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'completed')), "
            "created_at TEXT NOT NULL)"
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()[0]
        if "completed" not in schema:
            connection.execute("ALTER TABLE tasks RENAME TO tasks_old")
            connection.execute(
                "CREATE TABLE tasks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending' "
                "CHECK (status IN ('pending', 'done', 'completed')), "
                "created_at TEXT NOT NULL, owner_id INTEGER)"
            )
            connection.execute(
                "INSERT INTO tasks (id, title, status, created_at, owner_id) "
                "SELECT id, title, status, created_at, owner_id FROM tasks_old"
            )
            connection.execute("DROP TABLE tasks_old")
        connection.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            ("__legacy__", generate_password_hash(secrets.token_urlsafe(32))),
        )
        connection.execute(
            "UPDATE tasks SET owner_id = (SELECT id FROM users WHERE username = ?) "
            "WHERE owner_id IS NULL",
            ("__legacy__",),
        )
