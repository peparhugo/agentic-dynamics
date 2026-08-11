import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime


class BaseRepository(ABC):
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn


class UserRepository(BaseRepository):
    def create(self, username: str, password_hash: str) -> dict | None:
        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
                conn.commit()
                return {"id": cursor.lastrowid, "username": username}
            except sqlite3.IntegrityError:
                return None

    def get_by_username(self, username: str) -> dict | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            return dict(row) if row else None

    def get_by_id(self, user_id: int) -> dict | None:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return dict(row) if row else None


class TaskRepository(BaseRepository):
    def create(self, title: str, owner_id: int = None) -> dict:
        with self._get_connection() as conn:
            now = datetime.utcnow().isoformat()
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
                "owner_id": owner_id,
            }

    def get_all(self, owner_id: int = None) -> list[dict]:
        with self._get_connection() as conn:
            if owner_id is not None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                    (owner_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_by_id(self, task_id: int, owner_id: int = None) -> dict | None:
        with self._get_connection() as conn:
            if owner_id is not None:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                    (task_id, owner_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()
            return dict(row) if row else None

    def count(self, owner_id: int = None) -> int:
        with self._get_connection() as conn:
            if owner_id is not None:
                row = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
            return row[0] if row else 0

    def get_paginated(self, owner_id: int = None, cursor: int = None, limit: int = 20) -> tuple[list[dict], int]:
        actual_limit = min(limit, 100)
        with self._get_connection() as conn:
            if owner_id is not None:
                count_row = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE owner_id = ?", (owner_id,)
                ).fetchone()
                if cursor is not None:
                    rows = conn.execute(
                        "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                        (owner_id, cursor, actual_limit + 1),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                        (owner_id, actual_limit + 1),
                    ).fetchall()
            else:
                count_row = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
                if cursor is not None:
                    rows = conn.execute(
                        "SELECT * FROM tasks WHERE id < ? ORDER BY id DESC LIMIT ?",
                        (cursor, actual_limit + 1),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM tasks ORDER BY id DESC LIMIT ?",
                        (actual_limit + 1,),
                    ).fetchall()
            total = count_row[0] if count_row else 0
            items = [dict(r) for r in rows]
            return items, total

    def update(self, task_id: int, owner_id: int = None, title: str | None = None, status: str | None = None) -> dict | None:
        existing = self.get_by_id(task_id, owner_id)
        if existing is None:
            return None
        with self._get_connection() as conn:
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
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
                )
                conn.commit()
        return self.get_by_id(task_id, owner_id)
