"""Data access layer: repository classes for users and tasks.

All SQLite access lives here. Route handlers depend on these repository
classes instead of touching the database directly.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import sqlite3

from werkzeug.security import generate_password_hash


def get_db():
    """Return a new SQLite connection for the configured database.

    Reads the ``DATABASE`` path from the app module at call time so that
    test-level monkeypatching of ``app.DATABASE`` is honoured.
    """
    import app as app_module

    conn = sqlite3.connect(app_module.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the schema if it does not yet exist."""
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )
        conn.commit()


def migrate():
    """Add owner_id to pre-existing task tables without breaking existing data."""
    with get_db() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            conn.commit()


class BaseRepository(ABC):
    """Abstract base class declaring common CRUD operations."""

    table = ""
    id_column = "id"

    def __init__(self, connection_factory=None):
        self._connection_factory = connection_factory or get_db

    def _connect(self):
        return self._connection_factory()

    @staticmethod
    def _row_to_dict(row):
        return dict(row) if row is not None else None

    def _fetchone(self, sql, params=()):
        with self._connect() as conn:
            return conn.execute(sql, params).fetchone()

    def _fetchall(self, sql, params=()):
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()

    @abstractmethod
    def create(self, **kwargs):
        """Insert a new record and return it."""

    @abstractmethod
    def get_by_id(self, record_id):
        """Return the record with the given primary key."""

    @abstractmethod
    def list_all(self):
        """Return every record in the table."""

    @abstractmethod
    def update(self, record_id, **changes):
        """Update a record and return the updated version."""

    @abstractmethod
    def delete(self, record_id):
        """Remove the record with the given primary key."""


class UserRepository(BaseRepository):
    """Data access for the ``users`` table."""

    table = "users"

    def create(self, username, password):
        password_hash = generate_password_hash(password)
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username}

    def get_by_id(self, record_id):
        row = self._fetchone("SELECT * FROM users WHERE id = ?", (record_id,))
        return self._row_to_dict(row)

    def get_by_username(self, username):
        row = self._fetchone("SELECT * FROM users WHERE username = ?", (username,))
        return self._row_to_dict(row)

    def get_email(self, record_id):
        """Resolve a user's notification email address from their account."""
        row = self._fetchone("SELECT username FROM users WHERE id = ?", (record_id,))
        return f"{row['username']}@example.com" if row else None

    def list_all(self):
        rows = self._fetchall("SELECT * FROM users")
        return [self._row_to_dict(r) for r in rows]

    def update(self, record_id, **changes):
        fields = {"username": "username", "password_hash": "password_hash"}
        updates = []
        params = []
        for key, column in fields.items():
            if key in changes and changes[key] is not None:
                updates.append(f"{column} = ?")
                params.append(changes[key])
        if updates:
            params.append(record_id)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()
        return self.get_by_id(record_id)

    def delete(self, record_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (record_id,))
            conn.commit()


class TaskRepository(BaseRepository):
    """Data access for the ``tasks`` table."""

    table = "tasks"

    def create(self, owner_id, title):
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) "
                "VALUES (?, 'pending', ?, ?)",
                (title, now, owner_id),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "title": title,
                "status": "pending",
                "created_at": now,
                "owner_id": owner_id,
            }

    def get_by_id(self, record_id):
        row = self._fetchone("SELECT * FROM tasks WHERE id = ?", (record_id,))
        return self._row_to_dict(row)

    def list_all(self):
        rows = self._fetchall("SELECT * FROM tasks")
        return [self._row_to_dict(r) for r in rows]

    def get_for_owner(self, owner_id, task_id):
        row = self._fetchone(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        )
        return self._row_to_dict(row)

    def list_for_owner(self, owner_id):
        rows = self._fetchall(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )
        return [self._row_to_dict(r) for r in rows]

    def update_for_owner(self, owner_id, task_id, title=None, status=None):
        task = self.get_for_owner(owner_id, task_id)
        if task is None:
            return None
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            params.append(owner_id)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.get_for_owner(owner_id, task_id)

    def update(self, record_id, **changes):
        updates = []
        params = []
        for column in ("title", "status", "owner_id"):
            if column in changes and changes[column] is not None:
                updates.append(f"{column} = ?")
                params.append(changes[column])
        if updates:
            params.append(record_id)
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()
        return self.get_by_id(record_id)

    def delete(self, record_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (record_id,))
            conn.commit()
