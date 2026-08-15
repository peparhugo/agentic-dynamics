from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


class BaseRepository(ABC):
    """File-backed repository with atomic, shared CRUD operations."""

    def __init__(
        self,
        path_provider: Callable[[], Path],
        storage_name: str,
        lock: RLock | None = None,
    ) -> None:
        self._path_provider = path_provider
        self._storage_name = storage_name
        self._lock = lock or RLock()

    @property
    def path(self) -> Path:
        return self._path_provider()

    def initialize(self) -> None:
        with self._lock:
            if not self.path.exists():
                self._write([])

    def get_all(self) -> list[dict[str, Any]]:
        with self._lock:
            self.initialize()
            return self._read()

    def get_by_id(self, record_id: int) -> dict[str, Any] | None:
        return next(
            (record for record in self.get_all() if record["id"] == record_id),
            None,
        )

    def create(self, values: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.initialize()
            records = self._read()
            record = {
                "id": max((record["id"] for record in records), default=0) + 1,
                **self._build_record(values),
            }
            records.append(record)
            self._write(records)
            return record

    def update(
        self, record_id: int, values: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        with self._lock:
            self.initialize()
            records = self._read()
            record = next(
                (record for record in records if record["id"] == record_id), None
            )
            if record is None:
                return None
            record.update(values)
            self._write(records)
            return record

    def delete(self, record_id: int) -> bool:
        with self._lock:
            self.initialize()
            records = self._read()
            remaining = [record for record in records if record["id"] != record_id]
            if len(remaining) == len(records):
                return False
            self._write(remaining)
            return True

    @abstractmethod
    def _build_record(self, values: Mapping[str, Any]) -> dict[str, Any]:
        """Build storage fields for a newly created record."""

    def _read(self) -> list[dict[str, Any]]:
        try:
            with self.path.open(encoding="utf-8") as store:
                data = json.load(store)
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"{self._storage_name} storage is unreadable") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"{self._storage_name} storage is invalid")
        return data

    def _write(self, records: list[dict[str, Any]]) -> None:
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}."
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as store:
                json.dump(records, store, indent=2)
                store.write("\n")
            os.replace(temporary_name, path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise


class TaskRepository(BaseRepository):
    def __init__(
        self, path_provider: Callable[[], Path], lock: RLock | None = None
    ) -> None:
        super().__init__(path_provider, "task", lock)

    def initialize(self) -> None:
        with self._lock:
            super().initialize()
            tasks = self._read()
            migrated = False
            for task in tasks:
                if isinstance(task, dict) and "owner_id" not in task:
                    task["owner_id"] = None
                    migrated = True
            if migrated:
                self._write(tasks)

    def _build_record(self, values: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "title": values["title"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": values["owner_id"],
        }

    def create_for_owner(self, title: str, owner_id: int) -> dict[str, Any]:
        return self.create({"title": title, "owner_id": owner_id})

    def list_for_owner(
        self, owner_id: int, *, cursor: int | None = None, limit: int = 20
    ) -> tuple[list[dict[str, Any]], int | None, int]:
        tasks = [
            task for task in self.get_all() if task.get("owner_id") == owner_id
        ]
        tasks.sort(key=lambda task: task["created_at"], reverse=True)
        total = len(tasks)
        start = 0
        if cursor is not None:
            try:
                start = next(
                    index for index, task in enumerate(tasks) if task["id"] == cursor
                ) + 1
            except StopIteration as exc:
                raise ValueError("invalid cursor") from exc

        page = tasks[start : start + limit]
        next_cursor = page[-1]["id"] if start + limit < total else None
        return page, next_cursor, total

    def get_for_owner(
        self, task_id: int, owner_id: int
    ) -> dict[str, Any] | None:
        return next(
            (
                task
                for task in self.get_all()
                if task["id"] == task_id and task.get("owner_id") == owner_id
            ),
            None,
        )

    def update_for_owner(
        self,
        task_id: int,
        owner_id: int,
        *,
        title: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            self.initialize()
            tasks = self._read()
            task = next(
                (
                    task
                    for task in tasks
                    if task["id"] == task_id and task.get("owner_id") == owner_id
                ),
                None,
            )
            if task is None:
                return None
            if title is not None:
                task["title"] = title
            if status is not None:
                task["status"] = status
            self._write(tasks)
            return task


class UserRepository(BaseRepository):
    def __init__(
        self, path_provider: Callable[[], Path], lock: RLock | None = None
    ) -> None:
        super().__init__(path_provider, "user", lock)

    def _build_record(self, values: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "username": values["username"],
            "password_hash": generate_password_hash(
                values["password"], method="scrypt"
            ),
        }

    def create_user(self, username: str, password: str) -> dict[str, Any] | None:
        with self._lock:
            self.initialize()
            if any(user["username"] == username for user in self._read()):
                return None
            return self.create({"username": username, "password": password})

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        user = next(
            (user for user in self.get_all() if user["username"] == username), None
        )
        if user is None or not check_password_hash(user["password_hash"], password):
            return None
        return user
