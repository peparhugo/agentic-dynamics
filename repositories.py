"""
Data access layer — Repository pattern.

All SQLite queries live here. Route handlers in ``app.py`` only interact
with these repository objects, never with SQLite directly.
"""

from abc import ABC, abstractmethod
from datetime import datetime
import sqlite3


class BaseRepository(ABC):
    """Abstract base class providing common CRUD operations."""

    table: str = ""

    def __init__(self, get_db):
        self._get_db = get_db

    def _connect(self):
        return self._get_db()

    @abstractmethod
    def create(self, **fields) -> dict | None:
        """Insert a new record and return it, or ``None`` on conflict."""

    def find_by_id(self, entity_id) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ?", (entity_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_all(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table}").fetchall()
            return [dict(r) for r in rows]

    def update(self, entity_id, **fields) -> dict | None:
        if not fields:
            return self.find_by_id(entity_id)
        assignments = ", ".join(f"{column} = ?" for column in fields)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table} SET {assignments} WHERE id = ?",
                (*fields.values(), entity_id),
            )
            conn.commit()
        return self.find_by_id(entity_id)

    def delete(self, entity_id) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table} WHERE id = ?", (entity_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


class UserRepository(BaseRepository):
    table = "users"

    def create(self, username: str, password_hash: str, email: str | None = None) -> dict | None:
        with self._connect() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, password_hash, email),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "username": username, "email": email}
            except sqlite3.IntegrityError:
                return None

    def find_by_username(self, username: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None


class TaskRepository(BaseRepository):
    table = "tasks"

    def create(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
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

    def find_all(self, owner_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_by_id_and_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        task = self.find_by_id_and_owner(task_id, owner_id)
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
                params.append(task_id)
                params.append(owner_id)
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.find_by_id_and_owner(task_id, owner_id)
