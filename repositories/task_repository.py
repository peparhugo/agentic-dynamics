from datetime import datetime

from .base_repository import BaseRepository


class TaskRepository(BaseRepository):
    def create(self, title, owner_id):
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

    def find_by_id(self, task_id, owner_id):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
            return dict(row) if row else None

    def find_all_by_owner(self, owner_id):
        with self._get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def find_by_owner_paginated(self, owner_id, cursor=None, limit=20):
        with self._get_db() as conn:
            if cursor is not None:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? AND id < ? ORDER BY id DESC LIMIT ?",
                    (owner_id, cursor, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
                    (owner_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def count_by_owner(self, owner_id):
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM tasks WHERE owner_id = ?",
                (owner_id,),
            ).fetchone()
            return row["count"]

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
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                    params,
                )
                conn.commit()
        return self.find_by_id(task_id, owner_id)
