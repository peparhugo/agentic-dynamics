"""Repository pattern for data access layer."""

from abc import ABC, abstractmethod
from datetime import datetime
import sqlite3
import bcrypt


class BaseRepository(ABC):
    def __init__(self, get_db):
        self._get_db = get_db

    @abstractmethod
    def create(self, **kwargs):
        pass

    @abstractmethod
    def find_all(self, **kwargs):
        pass

    @abstractmethod
    def find_by_id(self, id, **kwargs):
        pass

    @abstractmethod
    def update(self, id, **kwargs):
        pass

    @abstractmethod
    def delete(self, id, **kwargs):
        pass


class TaskRepository(BaseRepository):
    def create(self, title, owner_id):
        with self._get_db() as conn:
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

    def find_all(self, owner_id):
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_paginated(self, owner_id, cursor=None, limit=20):
        limit = min(int(limit), 100)
        with self._get_db() as conn:
            count_row = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            total = count_row[0]

            if cursor is None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                    (owner_id, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY created_at DESC, id DESC LIMIT ?",
                    (owner_id, int(cursor), limit + 1),
                ).fetchall()

            data = [dict(r) for r in rows]
            if len(data) > limit:
                next_cursor = str(data[limit - 1]["id"])
                data = data[:limit]
            else:
                next_cursor = None

            return data, total, next_cursor

    def find_by_id(self, task_id, owner_id):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update(self, task_id, owner_id, title=None, status=None):
        task = self.find_by_id(task_id, owner_id)
        if task is None:
            return None
        with self._get_db() as conn:
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
                    f"UPDATE tasks SET {', '.join(updates)}"
                    " WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.find_by_id(task_id, owner_id)

    def delete(self, task_id, owner_id):
        with self._get_db() as conn:
            conn.execute(
                "DELETE FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            )
            conn.commit()


class UserRepository(BaseRepository):
    def create(self, username, password, email=None):
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        with self._get_db() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash, email)"
                    " VALUES (?, ?, ?)",
                    (username, password_hash, email),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "username": username, "email": email}
            except sqlite3.IntegrityError:
                return None

    def find_by_username(self, username):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def verify_password(self, user, password):
        return bcrypt.checkpw(
            password.encode("utf-8"), user["password_hash"].encode("utf-8")
        )

    def find_by_id(self, user_id, **kwargs):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_all(self, **kwargs):
        with self._get_db() as conn:
            rows = conn.execute("SELECT * FROM users").fetchall()
            return [dict(r) for r in rows]

    def update(self, user_id, **kwargs):
        pass

    def delete(self, user_id, **kwargs):
        with self._get_db() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
