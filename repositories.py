from abc import ABC, abstractmethod
import sqlite3
import os
from datetime import datetime, timedelta
import secrets
from werkzeug.security import generate_password_hash, check_password_hash


class BaseRepository(ABC):
    def get_db(self):
        db_path = os.environ.get("DATABASE", "tasks.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @abstractmethod
    def create(self, **kwargs):
        pass

    @abstractmethod
    def read(self, **kwargs):
        pass

    @abstractmethod
    def update(self, **kwargs):
        pass

    @abstractmethod
    def delete(self, **kwargs):
        pass


class UserRepository(BaseRepository):
    def create(self, username: str, password: str, email: str = None) -> dict:
        password_hash = generate_password_hash(password)
        now = datetime.utcnow().isoformat()
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, email if email else None, now),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username}

    def read(self, username: str = None, user_id: int = None) -> dict | None:
        with self.get_db() as conn:
            if username:
                row = conn.execute(
                    "SELECT * FROM users WHERE username = ?",
                    (username,),
                ).fetchone()
            elif user_id:
                row = conn.execute(
                    "SELECT * FROM users WHERE id = ?",
                    (user_id,),
                ).fetchone()
            else:
                return None
        return dict(row) if row else None

    def read_all(self) -> list:
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT id, username, role, created_at FROM users ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def username_exists(self, username: str) -> bool:
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
        return row is not None

    def verify_credentials(self, username: str, password: str) -> dict | None:
        user = self.read(username=username)
        if user is None or not check_password_hash(user["password_hash"], password):
            return None
        return user

    def update(self, **kwargs):
        raise NotImplementedError("UserRepository does not implement update")

    def delete(self, **kwargs):
        raise NotImplementedError("UserRepository does not implement delete")


class TokenRepository(BaseRepository):
    def __init__(self, token_ttl: int = 3600):
        super().__init__()
        self.token_ttl = token_ttl

    def create(self, user_id: int) -> str:
        token = secrets.token_hex(32)
        expires = (datetime.utcnow() + timedelta(seconds=self.token_ttl)).isoformat()
        with self.get_db() as conn:
            conn.execute(
                "INSERT INTO tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token, user_id, expires),
            )
            conn.commit()
        return token

    def read(self, token: str) -> dict | None:
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT u.* FROM users u JOIN tokens t ON u.id = t.user_id "
                "WHERE t.token = ? AND t.expires_at > ?",
                (token, datetime.utcnow().isoformat()),
            ).fetchone()
        return dict(row) if row else None

    def update(self, **kwargs):
        raise NotImplementedError("TokenRepository does not implement update")

    def delete(self, **kwargs):
        raise NotImplementedError("TokenRepository does not implement delete")


class TaskRepository(BaseRepository):
    def create(self, user_id: int, title: str, status: str = "pending") -> dict:
        now = datetime.utcnow().isoformat()
        with self.get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO tasks (user_id, title, status, created_at) VALUES (?, ?, ?, ?)",
                (user_id, title, status, now),
            )
            conn.commit()
            task_id = cursor.lastrowid
        return {
            "id": task_id,
            "title": title,
            "status": status,
            "created_at": now,
        }

    def read(self, task_id: int, user_id: int = None) -> dict | None:
        with self.get_db() as conn:
            if user_id is not None:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                    (task_id, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()
        return self._to_dict(row) if row else None

    def read_all(self, user_id: int) -> list:
        with self.get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [self._to_dict(row) for row in rows]

    def read_paginated(self, user_id: int, cursor: int = None, limit: int = 20) -> dict:
        limit = min(max(1, limit), 100)
        with self.get_db() as conn:
            if cursor is None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                    (user_id, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE user_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                    (user_id, cursor, limit + 1),
                ).fetchall()

            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]

        items = [self._to_dict(row) for row in rows[:limit]]
        next_cursor = rows[limit]["id"] if len(rows) > limit else None

        return {
            "data": items,
            "next_cursor": next_cursor,
            "total": total,
        }

    def update(self, task_id: int, user_id: int, title: str = None, status: str = None) -> dict | None:
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()

            if row is None:
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
                query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
                conn.execute(query, params)
                conn.commit()

        # Fetch updated row
        with self.get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()

        return self._to_dict(row)

    def delete(self, **kwargs):
        raise NotImplementedError("TaskRepository does not implement delete")

    def _to_dict(self, row):
        if row is None:
            return None
        return {
            "id": row["id"],
            "title": row["title"],
            "status": row["status"],
            "created_at": row["created_at"],
        }
