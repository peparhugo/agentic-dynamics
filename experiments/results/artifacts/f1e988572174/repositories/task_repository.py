from datetime import datetime
from repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    def create(self, title: str, owner_id: int) -> dict:
        with self._get_db() as conn:
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

    def find_all_by_owner(self, owner_id: int) -> list[dict]:
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_all_by_owner_paginated(self, owner_id: int, cursor: int | None = None, limit: int = 20) -> dict:
        limit = max(1, min(limit, 100))
        with self._get_db() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()[0]

            if cursor is not None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                    (owner_id, cursor, limit + 1),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                    (owner_id, limit + 1),
                ).fetchall()

            has_more = len(rows) > limit
            if has_more:
                rows = rows[:limit]

            data = [dict(r) for r in rows]
            next_cursor = str(data[-1]["id"]) if data and has_more else None

            return {
                "data": data,
                "next_cursor": next_cursor,
                "total": total,
            }

    def find_by_id_and_owner(self, task_id: int, owner_id: int) -> dict | None:
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        task = self.find_by_id_and_owner(task_id, owner_id)
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
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.find_by_id_and_owner(task_id, owner_id)
