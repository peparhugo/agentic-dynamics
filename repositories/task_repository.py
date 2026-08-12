"""
Repository for the ``tasks`` table.

Tasks are always scoped to an owner: every read/write method that touches a
specific row takes (and filters on) ``owner_id`` so a caller can never
accidentally read or mutate another user's task.
"""

from datetime import datetime

from repositories.base import BaseRepository


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        cursor = self.db.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) "
            "VALUES (?, 'pending', ?, ?)",
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

    def get_by_id(self, task_id: int, owner_id: int = None):
        if owner_id is None:
            row = self.db.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        else:
            row = self.db.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        return self._row_to_dict(row)

    def get_all(self, owner_id: int) -> list:
        rows = self.db.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update(self, task_id: int, owner_id: int, title: str = None, status: str = None):
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
            params.append(owner_id)
            self.db.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                params,
            )
            self.db.commit()
        return self.get_by_id(task_id, owner_id)
