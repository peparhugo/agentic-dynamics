"""
TaskRepository — all SQL for the ``tasks`` table lives here.

Tasks are always scoped to their owner, so the owner-aware lookups
(``get_by_id_for_owner``, ``get_page_for_owner``, ``count_for_owner``) are
the primary read methods used by the API (GET /tasks is cursor-paginated
via ``get_page_for_owner`` + ``count_for_owner``). ``get_all_for_owner``
is kept as a convenience/non-paginated read. The generic
``get_by_id``/``get_all`` from BaseRepository are also available but
intentionally unused by the routes since they would ignore ownership.
"""

from datetime import datetime
from typing import Optional

from .base import BaseRepository


class TaskRepository(BaseRepository):
    table_name = "tasks"

    def create(self, title: str, owner_id: int) -> dict:
        now = datetime.utcnow().isoformat()
        cursor = self._execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) "
            "VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }

    def get_all_for_owner(self, owner_id: int) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        )

    def get_page_for_owner(
        self, owner_id: int, cursor: Optional[int] = None, limit: int = 20
    ) -> list[dict]:
        """Return up to ``limit + 1`` rows ordered by id descending (which
        matches created_at descending since ids are assigned in insertion
        order), starting *after* ``cursor`` if given.

        Fetching one extra row lets the caller cheaply detect whether
        there's a next page without a separate COUNT query.
        """
        if cursor is not None:
            return self._fetchall(
                "SELECT * FROM tasks WHERE owner_id = ? AND id < ? "
                "ORDER BY id DESC LIMIT ?",
                (owner_id, cursor, limit + 1),
            )
        return self._fetchall(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
            (owner_id, limit + 1),
        )

    def count_for_owner(self, owner_id: int) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM tasks WHERE owner_id = ?", (owner_id,)
        )
        return row["cnt"] if row else 0

    def get_by_id_for_owner(self, task_id: int, owner_id: int) -> Optional[dict]:
        return self._fetchone(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        )

    def update(
        self,
        id_: int,
        owner_id: int,
        title: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[dict]:
        existing = self.get_by_id_for_owner(id_, owner_id)
        if existing is None:
            return None

        updates = []
        params: list = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if updates:
            params.append(id_)
            params.append(owner_id)
            self._execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                params,
            )

        return self.get_by_id_for_owner(id_, owner_id)
