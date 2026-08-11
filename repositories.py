import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class BaseRepository(ABC):
    def __init__(self, get_db):
        self._get_db = get_db

    def get_db(self):
        return self._get_db()

    @abstractmethod
    def find_by_id(self, id):
        pass


class UserRepository(BaseRepository):
    def find_by_id(self, user_id):
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

    def find_by_username(self, username):
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            return dict(row) if row else None

    def create(self, username, password_hash):
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            return cursor.lastrowid


class TaskRepository(BaseRepository):
    def find_by_id(self, task_id):
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            return dict(row) if row else None

    def find_by_id_and_owner(self, task_id, owner_id):
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def find_by_owner(self, owner_id):
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def create(self, title, owner_id):
        now = datetime.now(timezone.utc).isoformat()
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
                (title, now, owner_id),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "title": title,
                "status": "pending",
                "created_at": now,
            }

    def update(self, task_id, updates):
        if not updates:
            return self.find_by_id(task_id)
        with self.get_db() as conn:
            set_clauses = []
            params = []
            for col, val in updates.items():
                set_clauses.append(f"{col} = ?")
                params.append(val)
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?", params
            )
            conn.commit()
            return self.find_by_id(task_id)
