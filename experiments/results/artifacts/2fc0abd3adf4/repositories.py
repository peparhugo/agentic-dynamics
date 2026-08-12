from abc import ABC, abstractmethod
from datetime import datetime
import sqlite3
import bcrypt


class BaseRepository(ABC):
    def __init__(self, get_db_func):
        self._get_db = get_db_func

    def _fetch_one(self, query, params=()):
        with self._get_db() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def _fetch_all(self, query, params=()):
        with self._get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def _execute_write(self, query, params=()):
        with self._get_db() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor


class UserRepository(BaseRepository):
    def create(self, username: str, password: str, email: str | None = None) -> dict | None:
        password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt()
        ).decode()
        try:
            cursor = self._execute_write(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            result = {"id": cursor.lastrowid, "username": username}
            if email:
                result["email"] = email
            return result
        except sqlite3.IntegrityError:
            return None

    def find_by_username(self, username: str) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM users WHERE username = ?", (username,)
        )

    def find_by_id(self, user_id: int) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )


class TaskRepository(BaseRepository):
    def create(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        cursor = self._execute_write(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
        }

    def find_all(self, owner_id: int) -> list[dict]:
        return self._fetch_all(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )

    def find_by_id(self, task_id: int, owner_id: int) -> dict | None:
        return self._fetch_one(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )

    def exists(self, task_id: int) -> bool:
        return self._fetch_one("SELECT 1 FROM tasks WHERE id = ?", (task_id,)) is not None

    def find_all_paginated(self, owner_id: int, cursor: int | None = None, limit: int = 20) -> tuple[list[dict], str | None, int]:
        total = self._fetch_one(
            "SELECT COUNT(*) as cnt FROM tasks WHERE owner_id = ?",
            (owner_id,),
        )
        total = total["cnt"] if total else 0

        if cursor is None:
            rows = self._fetch_all(
                "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                (owner_id, limit + 1),
            )
        else:
            rows = self._fetch_all(
                "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                (owner_id, cursor, limit + 1),
            )

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        next_cursor = str(rows[-1]["id"]) if (has_more and rows) else None
        return rows, next_cursor, total

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        task = self.find_by_id(task_id, owner_id)
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
            self._execute_write(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                tuple(params),
            )
        return self.find_by_id(task_id, owner_id)
