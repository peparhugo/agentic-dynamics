"""Repositories for the task API's JSON-backed persistence."""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    """Provide common CRUD operations for a JSON list data store."""

    def __init__(self, path_provider: Callable[[], Path], description: str):
        self._path_provider = path_provider
        self._description = description

    @property
    @abstractmethod
    def record_type(self) -> str:
        """Name of the records managed by this repository."""

    def initialize(self) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("[]\n", encoding="utf-8")

    def list_all(self) -> list[dict]:
        self.initialize()
        try:
            records = json.loads(self._path().read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise RuntimeError(f"{self._description} contains invalid JSON") from error
        if not isinstance(records, list):
            raise RuntimeError(f"{self._description} must contain a JSON list")
        return records

    def get_by_id(self, record_id: int) -> dict | None:
        return next((record for record in self.list_all() if record["id"] == record_id), None)

    def create(self, values: dict) -> dict:
        records = self.list_all()
        record = {"id": max((item["id"] for item in records), default=0) + 1, **values}
        records.append(record)
        self._write_all(records)
        return record

    def update(self, record_id: int, values: dict) -> dict | None:
        records = self.list_all()
        record = next((item for item in records if item["id"] == record_id), None)
        if record is None:
            return None
        record.update(values)
        self._write_all(records)
        return record

    def delete(self, record_id: int) -> bool:
        records = self.list_all()
        remaining = [record for record in records if record["id"] != record_id]
        if len(remaining) == len(records):
            return False
        self._write_all(remaining)
        return True

    def _path(self) -> Path:
        return self._path_provider()

    def _write_all(self, records: list[dict]) -> None:
        path = self._path()
        temporary_path = path.with_suffix(f"{path.suffix}.tmp")
        temporary_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        temporary_path.replace(path)


class TaskRepository(BaseRepository):
    @property
    def record_type(self) -> str:
        return "task"

    def migrate_ownership(self) -> None:
        tasks = self.list_all()
        if any("owner_id" not in task for task in tasks):
            for task in tasks:
                task.setdefault("owner_id", None)
            self._write_all(tasks)

    def create_task(self, title: str, owner_id: int) -> dict:
        return self.create(
            {
                "title": title,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "owner_id": owner_id,
            }
        )

    def list_for_owner(self, owner_id: int) -> list[dict]:
        tasks = (task for task in self.list_all() if task.get("owner_id") == owner_id)
        return sorted(tasks, key=lambda task: task["created_at"], reverse=True)

    def list_page_for_owner(self, owner_id: int, cursor: int | None, limit: int) -> tuple[list[dict], int | None, int]:
        tasks = self.list_for_owner(owner_id)
        total = len(tasks)
        if cursor is not None:
            cursor_index = next((index for index, task in enumerate(tasks) if task["id"] == cursor), None)
            if cursor_index is None:
                return [], None, total
            tasks = tasks[cursor_index + 1 :]
        page = tasks[:limit]
        next_cursor = page[-1]["id"] if len(tasks) > limit else None
        return page, next_cursor, total

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        task = self.get_by_id(task_id)
        return task if task is not None and task.get("owner_id") == owner_id else None

    def update_for_owner(
        self, task_id: int, owner_id: int, title: str | None = None, status: str | None = None
    ) -> dict | None:
        if self.get_for_owner(task_id, owner_id) is None:
            return None
        values = {}
        if title is not None:
            values["title"] = title
        if status is not None:
            values["status"] = status
        return self.update(task_id, values)


class UserRepository(BaseRepository):
    @property
    def record_type(self) -> str:
        return "user"

    def create_user(self, username: str, password: str) -> dict | None:
        if self.get_by_username(username) is not None:
            return None
        return self.create({"username": username, "password_hash": generate_password_hash(password)})

    def get_by_username(self, username: str) -> dict | None:
        return next((user for user in self.list_all() if user["username"] == username), None)
