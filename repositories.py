import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    def __init__(self, db):
        self.db = db

    @abstractmethod
    def create(self, **kwargs):
        pass

    @abstractmethod
    def get_by_id(self, id):
        pass


class UserRepository(BaseRepository):
    def create(self, username, password, email=None):
        password_hash = generate_password_hash(password)
        try:
            cursor = self.db.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            self.db.commit()
            return {"id": cursor.lastrowid, "username": username, "email": email}
        except sqlite3.IntegrityError:
            return None

    def get_by_id(self, id):
        row = self.db.execute(
            "SELECT * FROM users WHERE id = ?", (id,)
        ).fetchone()
        return dict(row) if row else None

    def get_by_username(self, username):
        row = self.db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None

    def get_email(self, user_id):
        row = self.db.execute(
            "SELECT email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row["email"] if row else None


class TaskRepository(BaseRepository):
    def create(self, title, owner_id):
        now = datetime.utcnow().isoformat()
        cursor = self.db.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        self.db.commit()
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }

    def get_by_id(self, task_id, owner_id):
        row = self.db.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        return dict(row) if row else None

    def list_by_owner(self, owner_id):
        rows = self.db.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update(self, task_id, owner_id, title=None, status=None):
        task = self.get_by_id(task_id, owner_id)
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
            self.db.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            self.db.commit()
        return self.get_by_id(task_id, owner_id)
