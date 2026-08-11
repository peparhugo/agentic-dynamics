from abc import ABC, abstractmethod
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    def __init__(self, db_path=None):
        self._db_path = db_path or os.environ.get("DATABASE", "todos.db")

    def _get_db(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @abstractmethod
    def find_all(self, **filters):
        pass

    @abstractmethod
    def find_by_id(self, id, **filters):
        pass

    @abstractmethod
    def create(self, **data):
        pass

    @abstractmethod
    def update(self, id, **data):
        pass

    @abstractmethod
    def delete(self, id, **filters):
        pass


class UserRepository(BaseRepository):
    def find_all(self, **filters):
        with self._get_db() as conn:
            rows = conn.execute("SELECT id, username FROM users").fetchall()
            return [dict(r) for r in rows]

    def find_by_id(self, id, **filters):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (id,)
            ).fetchone()
            return dict(row) if row else None

    def find_by_username(self, username):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def create(self, **data):
        with self._get_db() as conn:
            try:
                password_hash = generate_password_hash(data["password"])
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (data["username"], password_hash),
                )
                return {"id": cursor.lastrowid, "username": data["username"]}
            except sqlite3.IntegrityError:
                return None

    def update(self, id, **data):
        with self._get_db() as conn:
            updates = []
            params = []
            for key, value in data.items():
                if value is not None:
                    updates.append(f"{key} = ?")
                    params.append(value)
            if updates:
                params.append(id)
                conn.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params
                )
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (id,)
            ).fetchone()
            return dict(row) if row else None

    def delete(self, id, **filters):
        with self._get_db() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (id,))


class TaskRepository(BaseRepository):
    def find_all(self, **filters):
        owner_id = filters.get("owner_id")
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_by_id(self, id, **filters):
        owner_id = filters.get("owner_id")
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def fetch_by_id(self, id, **filters):
        return self.find_by_id(id, **filters)

    def create(self, **data):
        with self._get_db() as conn:
            now = datetime.utcnow().isoformat()
            cursor = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) "
                "VALUES (?, 'pending', ?, ?)",
                (data["title"], now, data["owner_id"]),
            )
            return {
                "id": cursor.lastrowid,
                "title": data["title"],
                "status": "pending",
                "created_at": now,
                "owner_id": data["owner_id"],
            }

    def update(self, id, **data):
        owner_id = data.pop("owner_id", None)
        task = self.find_by_id(id, owner_id=owner_id)
        if task is None:
            return None
        with self._get_db() as conn:
            updates = []
            params = []
            for key, value in data.items():
                if value is not None:
                    updates.append(f"{key} = ?")
                    params.append(value)
            if updates:
                params.append(id)
                params.append(owner_id)
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} "
                    "WHERE id = ? AND owner_id = ?",
                    params,
                )
        return self.find_by_id(id, owner_id=owner_id)

    def delete(self, id, **filters):
        owner_id = filters.get("owner_id")
        with self._get_db() as conn:
            conn.execute(
                "DELETE FROM tasks WHERE id = ? AND owner_id = ?",
                (id, owner_id),
            )
