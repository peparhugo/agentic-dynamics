"""TaskRepository — all SQL for the ``tasks`` table."""

from datetime import datetime

from .base import BaseRepository


class TaskRepository(BaseRepository):
    def create(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        cursor = self._execute(
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

    def get_all(self, owner_id: int) -> list[dict]:
        return self._fetch_all(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
        )

    def get_by_id(self, task_id: int, owner_id: int) -> dict | None:
        return self._fetch_one(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        )

    def update(
        self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None
    ) -> dict | None:
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
            self._execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params
            )
        return self.get_by_id(task_id, owner_id)
