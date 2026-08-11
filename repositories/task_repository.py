from datetime import datetime
from .base_repository import BaseRepository


class TaskRepository(BaseRepository):
    def create(self, title: str, owner_id: int) -> dict:
        with self._get_conn() as conn:
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
            }

    def get_all(self, owner_id: int):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_all_paginated(self, owner_id: int, cursor: int | None = None, limit: int = 20):
        with self._get_conn() as conn:
            if cursor is not None:
                rows = conn.execute(
                    "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? AND id < ? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, cursor, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC LIMIT ?",
                    (owner_id, limit + 1),
                ).fetchall()
            has_more = len(rows) > limit
            data = [dict(r) for r in rows[:limit]]
            next_cursor = str(data[-1]["id"]) if has_more and data else None
            return data, next_cursor

    def count_all(self, owner_id: int) -> int:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            return row[0]

    def get_by_id(self, task_id: int, owner_id: int) -> dict | None:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        task = self.get_by_id(task_id, owner_id)
        if task is None:
            return None
        with self._get_conn() as conn:
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
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params
                )
                conn.commit()
        return self.get_by_id(task_id, owner_id)
