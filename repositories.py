"""Repository-pattern data access layer for the task management API.

All SQLite access lives here. Route handlers in ``app.py`` depend only on the
repository interfaces defined in this module and never touch SQL directly.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash


class BaseRepository(ABC):
    """Abstract base repository declaring the common CRUD contract."""

    def __init__(self, get_db):
        self.get_db = get_db

    @abstractmethod
    def create(self, **kwargs):
        """Insert a new record."""

    @abstractmethod
    def get(self, record_id, **kwargs):
        """Fetch a single record by its primary key."""

    @abstractmethod
    def all(self, **kwargs):
        """Fetch all records (optionally filtered)."""

    @abstractmethod
    def update(self, record_id, **kwargs):
        """Update an existing record."""

    @abstractmethod
    def delete(self, record_id, **kwargs):
        """Delete an existing record."""


class TaskRepository(BaseRepository):
    """Repository for ``tasks`` rows."""

    def create(self, title, owner_id):
        with self.get_db() as conn:
            now = datetime.utcnow().isoformat()
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id)"
                " VALUES (?, 'pending', ?, ?)",
                (title, now, owner_id),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "title": title,
                "status": "pending",
                "created_at": now,
            }

    def get(self, task_id, owner_id):
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def all(self, owner_id):
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def update(self, task_id, owner_id, title=None, status=None):
        task = self.get(task_id, owner_id)
        if task is None:
            return None
        with self.get_db() as conn:
            updates, params = [], []
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if updates:
                params.append(task_id)
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()
        return self.get(task_id, owner_id)

    def delete(self, task_id, owner_id):
        with self.get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            )
            conn.commit()
            return cursor.rowcount


class UserRepository(BaseRepository):
    """Repository for ``users`` rows."""

    def create(self, username, password, email=None):
        with self.get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing is not None:
                return None
            if email is None:
                email = f"{username}@example.com"
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), email),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username, "email": email}

    def get(self, user_id):
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_username(self, username):
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def authenticate(self, username, password):
        row = self.get_by_username(username)
        if row is None:
            return None
        if not check_password_hash(row["password_hash"], password):
            return None
        return row

    def all(self):
        with self.get_db() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(r) for r in rows]

    def update(self, user_id, **kwargs):
        with self.get_db() as conn:
            fields, params = [], []
            for column in ("username", "password_hash", "email"):
                if column in kwargs:
                    fields.append(f"{column} = ?")
                    params.append(kwargs[column])
            if fields:
                params.append(user_id)
                conn.execute(
                    f"UPDATE users SET {', '.join(fields)} WHERE id = ?", params
                )
                conn.commit()
        return self.get(user_id)

    def delete(self, user_id):
        with self.get_db() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount


def create_schema(get_db):
    """Create the database tables and apply migrations."""
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        user_cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()
