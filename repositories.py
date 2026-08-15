"""Data access layer implemented with the Repository pattern.

All SQL for persisting users and tasks lives in the repository classes
below. Route handlers should never touch SQLite directly; they should go
through these repositories instead.
"""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    """Abstract base class providing common CRUD operations.

    Concrete repositories must set ``table_name``.
    """

    @property
    @abstractmethod
    def table_name(self) -> str:
        """The name of the table this repository manages."""
        raise NotImplementedError

    def __init__(self, get_conn):
        self._get_conn = get_conn

    def _connect(self):
        return self._get_conn()

    def get_all(self):
        with self._connect() as conn:
            rows = conn.execute(f"SELECT * FROM {self.table_name}").fetchall()
            return [dict(r) for r in rows]

    def get_by_id(self, record_id):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (record_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_by(self, field, value):
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {self.table_name} WHERE {field} = ?", (value,)
            ).fetchone()
            return dict(row) if row else None

    def create(self, data):
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        values = list(data.values())
        with self._connect() as conn:
            cursor = conn.execute(
                f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})",
                values,
            )
            conn.commit()
            data["id"] = cursor.lastrowid
            return data

    def update(self, record_id, data):
        assignments = ", ".join(f"{key} = ?" for key in data)
        values = list(data.values()) + [record_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE {self.table_name} SET {assignments} WHERE id = ?", values
            )
            conn.commit()
        return self.get_by_id(record_id)

    def delete(self, record_id):
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (record_id,)
            )
            conn.commit()
            return cursor.rowcount > 0


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create(self, title, owner_id):
        now = datetime.utcnow().isoformat()
        return super().create(
            {
                "title": title,
                "status": "pending",
                "created_at": now,
                "owner_id": owner_id,
            }
        )

    def list_by_owner(self, owner_id):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_by_owner_paginated(self, owner_id, cursor=None, limit=20):
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()["c"]

            if cursor is None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? "
                    "ORDER BY id DESC LIMIT ?",
                    (owner_id, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? AND id < ? "
                    "ORDER BY id DESC LIMIT ?",
                    (owner_id, cursor, limit + 1),
                ).fetchall()

        has_more = len(rows) > limit
        page = rows[:limit]
        data = [dict(r) for r in page]
        next_cursor = str(page[-1]["id"]) if has_more and page else None
        return {"data": data, "next_cursor": next_cursor, "total": total}

    def get(self, task_id, owner_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update(self, task_id, owner_id, title=None, status=None):
        task = self.get(task_id, owner_id)
        if task is None:
            return None
        updates = {}
        if title is not None:
            updates["title"] = title
        if status is not None:
            updates["status"] = status
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values()) + [task_id, owner_id]
            with self._connect() as conn:
                conn.execute(
                    f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                    values,
                )
                conn.commit()
        return self.get(task_id, owner_id)


class UserRepository(BaseRepository):
    table_name = "users"

    def create(self, username, password, email=None):
        password_hash = generate_password_hash(password)
        email = (email or "").strip() or f"{username}@example.com"
        try:
            created = super().create(
                {
                    "username": username,
                    "password_hash": password_hash,
                    "email": email,
                }
            )
        except sqlite3.IntegrityError:
            return None
        return {"id": created["id"], "username": username, "email": email}

    def find_by_username(self, username):
        return self.find_by("username", username)

    def find_by_id(self, user_id):
        return self.get_by_id(user_id)
