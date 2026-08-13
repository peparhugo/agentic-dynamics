"""
Repository for task records, backed by a flat JSON file.

Writes are atomic (write to a temp file, then os.replace) and serialized
with a lock so concurrent requests within one process don't corrupt the
file.
"""

import os
from datetime import datetime

from base_repository import BaseRepository


def _now_iso() -> str:
    # Always include microseconds (fixed width) so plain string comparison
    # sorts chronologically, e.g. for "ORDER BY created_at desc".
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")


class TaskRepository(BaseRepository):
    def __init__(self, path: str):
        super().__init__(path)
        existed = os.path.exists(path)
        self._ensure_initialized({"next_id": 1, "tasks": []})
        if existed:
            self._migrate_add_owner_id()

    def _migrate_add_owner_id(self) -> None:
        # Tasks written before owner_id existed are left owner-less (None)
        # rather than dropped, so pre-existing data keeps loading cleanly.
        with self._lock:
            data = self._read()
            changed = False
            for task in data["tasks"]:
                if "owner_id" not in task:
                    task["owner_id"] = None
                    changed = True
            if changed:
                self._write(data)

    def create(self, title: str, owner_id: int) -> dict:
        with self._lock:
            data = self._read()
            task = {
                "id": data["next_id"],
                "title": title,
                "status": "pending",
                "created_at": _now_iso(),
                "owner_id": owner_id,
            }
            data["tasks"].append(task)
            data["next_id"] += 1
            self._write(data)
            return task

    def list_page(self, owner_id: int, cursor: int | None = None, limit: int = 20) -> dict | None:
        # Cursor is the id of the last item the caller already has; ordering
        # matches the previous list_all behavior (newest first), with id as
        # a tiebreaker for created_at collisions.
        data = self._read()
        tasks = [t for t in data["tasks"] if t["owner_id"] == owner_id]
        tasks.sort(key=lambda t: (t["created_at"], t["id"]), reverse=True)
        total = len(tasks)

        start = 0
        if cursor is not None:
            index = next((i for i, t in enumerate(tasks) if t["id"] == cursor), None)
            if index is None:
                return None
            start = index + 1

        page = tasks[start:start + limit]
        next_cursor = page[-1]["id"] if start + len(page) < total else None
        return {"data": page, "next_cursor": next_cursor, "total": total}

    def get(self, task_id: int, owner_id: int) -> dict | None:
        data = self._read()
        for task in data["tasks"]:
            if task["id"] == task_id and task["owner_id"] == owner_id:
                return task
        return None

    def update(self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        with self._lock:
            data = self._read()
            for task in data["tasks"]:
                if task["id"] == task_id and task["owner_id"] == owner_id:
                    if title is not None:
                        task["title"] = title
                    if status is not None:
                        task["status"] = status
                    self._write(data)
                    return task
            return None
