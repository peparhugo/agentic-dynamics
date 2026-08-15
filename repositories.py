import json
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    """Thread-safe repository with common CRUD operations."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.initialize()

    def initialize(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write([])

    def _read(self) -> list[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as file:
            records = json.load(file)
        if not isinstance(records, list):
            raise ValueError("repository storage must contain a JSON array")
        return records

    def _write(self, records: list[dict[str, Any]]) -> None:
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, self.path)

    @abstractmethod
    def _build_record(self, record_id: int, **values: Any) -> dict[str, Any]:
        """Build a persisted record from repository-specific values."""

    def _can_create(
        self, records: list[dict[str, Any]], **values: Any
    ) -> bool:
        return True

    def create(self, **values: Any) -> dict[str, Any] | None:
        with self._lock:
            records = self._read()
            if not self._can_create(records, **values):
                return None
            record_id = max((record["id"] for record in records), default=0) + 1
            record = self._build_record(record_id, **values)
            records.append(record)
            self._write(records)
            return record

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def get(self, record_id: int) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (record for record in self._read() if record["id"] == record_id),
                None,
            )

    def update(
        self, record_id: int, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._lock:
            records = self._read()
            for record in records:
                if record["id"] == record_id:
                    record.update(changes)
                    self._write(records)
                    return record
            return None

    def delete(self, record_id: int) -> bool:
        with self._lock:
            records = self._read()
            remaining = [record for record in records if record["id"] != record_id]
            if len(remaining) == len(records):
                return False
            self._write(remaining)
            return True


class TaskRepository(BaseRepository):
    def initialize(self) -> None:
        super().initialize()
        with self._lock:
            tasks = self._read()
            if any("owner_id" not in task for task in tasks):
                for task in tasks:
                    task.setdefault("owner_id", None)
                self._write(tasks)

    def _build_record(self, record_id: int, **values: Any) -> dict[str, Any]:
        return {
            "id": record_id,
            "title": values["title"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": values["owner_id"],
        }

    def list(self, owner_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(
                (task for task in self._read() if task.get("owner_id") == owner_id),
                key=lambda task: task["created_at"],
                reverse=True,
            )

    def get(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (
                    task
                    for task in self._read()
                    if task["id"] == task_id and task.get("owner_id") == owner_id
                ),
                None,
            )

    def update(
        self, task_id: int, owner_id: int, changes: dict[str, Any]
    ) -> dict[str, Any] | None:
        with self._lock:
            tasks = self._read()
            for task in tasks:
                if task["id"] == task_id and task.get("owner_id") == owner_id:
                    task.update(changes)
                    self._write(tasks)
                    return task
            return None


class UserRepository(BaseRepository):
    def _can_create(
        self, records: list[dict[str, Any]], **values: Any
    ) -> bool:
        return not any(user["username"] == values["username"] for user in records)

    def _build_record(self, record_id: int, **values: Any) -> dict[str, Any]:
        return {
            "id": record_id,
            "username": values["username"],
            "email": values.get("email") or values["username"],
            "password_hash": generate_password_hash(values["password"]),
        }

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (user for user in self._read() if user["username"] == username),
                None,
            )
