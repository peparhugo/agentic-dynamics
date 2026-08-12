from abc import ABC
from datetime import datetime


class BaseRepository(ABC):
    def __init__(self, get_db):
        self._get_db = get_db

    def _execute_and_commit(self, query, params=()):
        with self._get_db() as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor

    def _fetchone(self, query, params=()):
        with self._get_db() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def _fetchall(self, query, params=()):
        with self._get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]


class UserRepository(BaseRepository):
    def create(self, username: str, password_hash: str, email: str | None = None) -> int:
        cursor = self._execute_and_commit(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        return cursor.lastrowid

    def find_by_username(self, username: str) -> dict | None:
        return self._fetchone("SELECT * FROM users WHERE username = ?", (username,))

    def find_by_id(self, user_id: int) -> dict | None:
        return self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))


class TaskRepository(BaseRepository):
    def create(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        cursor = self._execute_and_commit(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }

    def find_all_by_owner(self, owner_id: int) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
        )

    def find_all_by_owner_paginated(self, owner_id: int, cursor: int | None = None, limit: int = 20) -> tuple[list[dict], int, str | None]:
        total_row = self._fetchone(
            "SELECT COUNT(*) as cnt FROM tasks WHERE owner_id = ?", (owner_id,)
        )
        total = total_row["cnt"] if total_row else 0

        if cursor is not None:
            rows = self._fetchall(
                "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (owner_id, cursor, limit + 1),
            )
        else:
            rows = self._fetchall(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (owner_id, limit + 1),
            )

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        next_cursor = str(rows[-1]["id"]) if has_more else None
        return rows, total, next_cursor

    def find_by_id_and_owner(self, task_id: int, owner_id: int) -> dict | None:
        return self._fetchone(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        )

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        task = self.find_by_id_and_owner(task_id, owner_id)
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
            self._execute_and_commit(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", tuple(params)
            )
        return self.find_by_id_and_owner(task_id, owner_id)
