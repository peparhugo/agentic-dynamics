"""
Flat-file (JSON) storage for the Task Management API.

No database is used — tasks persist to a single JSON file on disk. Writes are
atomic (write to a temp file, then os.replace) and serialized with a lock so
concurrent requests within one process don't corrupt the file.
"""

import json
import os
import threading
from datetime import datetime


def _now_iso() -> str:
    # Always include microseconds (fixed width) so plain string comparison
    # sorts chronologically, e.g. for "ORDER BY created_at desc".
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")


class TaskStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        if not os.path.exists(self.path):
            self._write({"next_id": 1, "tasks": []})

    def _read(self) -> dict:
        with open(self.path, "r") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)

    def create(self, title: str) -> dict:
        with self._lock:
            data = self._read()
            task = {
                "id": data["next_id"],
                "title": title,
                "status": "pending",
                "created_at": _now_iso(),
            }
            data["tasks"].append(task)
            data["next_id"] += 1
            self._write(data)
            return task

    def list_all(self) -> list:
        data = self._read()
        return sorted(data["tasks"], key=lambda t: t["created_at"], reverse=True)

    def get(self, task_id: int) -> dict | None:
        data = self._read()
        for task in data["tasks"]:
            if task["id"] == task_id:
                return task
        return None

    def update(self, task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
        with self._lock:
            data = self._read()
            for task in data["tasks"]:
                if task["id"] == task_id:
                    if title is not None:
                        task["title"] = title
                    if status is not None:
                        task["status"] = status
                    self._write(data)
                    return task
            return None
