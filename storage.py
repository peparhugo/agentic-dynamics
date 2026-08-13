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
        else:
            self._migrate_add_owner_id()

    def _read(self) -> dict:
        with open(self.path, "r") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)

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

    def list_all(self, owner_id: int) -> list:
        data = self._read()
        tasks = [t for t in data["tasks"] if t["owner_id"] == owner_id]
        return sorted(tasks, key=lambda t: t["created_at"], reverse=True)

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


class UserStore:
    """Flat-file (JSON) storage for users, mirroring TaskStore's design."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        if not os.path.exists(self.path):
            self._write({"next_id": 1, "users": []})

    def _read(self) -> dict:
        with open(self.path, "r") as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.path)

    def create(self, username: str, password_hash: str) -> dict:
        with self._lock:
            data = self._read()
            user = {
                "id": data["next_id"],
                "username": username,
                "password_hash": password_hash,
            }
            data["users"].append(user)
            data["next_id"] += 1
            self._write(data)
            return user

    def get_by_username(self, username: str) -> dict | None:
        data = self._read()
        for user in data["users"]:
            if user["username"] == username:
                return user
        return None

    def get_by_id(self, user_id: int) -> dict | None:
        data = self._read()
        for user in data["users"]:
            if user["id"] == user_id:
                return user
        return None
