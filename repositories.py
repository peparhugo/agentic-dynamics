"""
Repository pattern data access layer for the todo API.

All SQLite queries live here. Route handlers in ``app.py`` must go through
these repositories instead of touching the database directly.
"""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    """Abstract base repository providing common CRUD operations."""

    def __init__(self, get_db):
        self._get_db = get_db

    def _connect(self):
        return self._get_db()

    @abstractmethod
    def create(self, *args, **kwargs):
        """Insert a new entity and return it."""

    @abstractmethod
    def get_all(self, *args, **kwargs):
        """Return all entities."""

    @abstractmethod
    def get_by_id(self, entity_id, *args, **kwargs):
        """Return a single entity by id, or None if not found."""

    @abstractmethod
    def update(self, entity_id, *args, **kwargs):
        """Update an entity and return the updated entity, or None."""

    @abstractmethod
    def delete(self, entity_id, *args, **kwargs):
        """Delete an entity."""


class UserRepository(BaseRepository):
    """Data access for the ``users`` table."""

    def create(self, username, password):
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "username": username}
            except sqlite3.IntegrityError:
                return None

    def get_all(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(row) for row in rows]

    def get_by_id(self, entity_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (entity_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_username(self, username):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def update(self, entity_id, **kwargs):
        with self._connect() as conn:
            updates = []
            params = []
            for column, value in kwargs.items():
                updates.append(f"{column} = ?")
                params.append(value)
            if updates:
                params.append(entity_id)
                conn.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()
        return self.get_by_id(entity_id)

    def delete(self, entity_id):
        with self._connect() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (entity_id,))
            conn.commit()


class TaskRepository(BaseRepository):
    """Data access for the ``tasks`` table."""

    def create(self, title, owner_id):
        with self._connect() as conn:
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
                "owner_id": owner_id,
            }

    def get_all(self, owner_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_by_id(self, entity_id, owner_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (entity_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update(self, entity_id, owner_id, title=None, status=None):
        task = self.get_by_id(entity_id, owner_id)
        if task is None:
            return None
        with self._connect() as conn:
            updates = []
            params = []
            if title is not None:
                updates.append("title = ?")
                params.append(title)
            if status is not None:
                updates.append("status = ?")
                params.append(status)
            if updates:
                params.append(entity_id)
                params.append(owner_id)
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.get_by_id(entity_id, owner_id)

    def delete(self, entity_id, owner_id=None):
        with self._connect() as conn:
            if owner_id is None:
                conn.execute("DELETE FROM tasks WHERE id = ?", (entity_id,))
            else:
                conn.execute(
                    "DELETE FROM tasks WHERE id = ? AND owner_id = ?",
                    (entity_id, owner_id),
                )
            conn.commit()
