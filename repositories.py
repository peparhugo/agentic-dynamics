"""Repositories for the task application's persistent data."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from typing import Any

from werkzeug.security import generate_password_hash


_storage_lock = Lock()


def _empty_store() -> dict[str, Any]:
    return {"next_id": 1, "next_user_id": 1, "tasks": [], "users": []}


def _read_store(database: str) -> dict[str, Any]:
    path = Path(database)
    if not path.exists():
        return _empty_store()
    with path.open(encoding="utf-8") as data_file:
        return json.load(data_file)


def _write_store(database: str, store: dict[str, Any]) -> None:
    path = Path(database)
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("w", encoding="utf-8") as data_file:
        json.dump(store, data_file, indent=2)
        data_file.write("\n")
    os.replace(temporary_path, path)


def initialize_store(database: str) -> None:
    """Initialize the data store and apply additive schema migrations."""
    path = Path(database)
    with _storage_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            _write_store(database, _empty_store())
            return

        store = _read_store(database)
        changed = False
        if "next_user_id" not in store:
            store["next_user_id"] = 1
            changed = True
        if "users" not in store:
            store["users"] = []
            changed = True
        for task in store.get("tasks", []):
            if "owner_id" not in task:
                task["owner_id"] = None
                changed = True
        if changed:
            _write_store(database, store)


class BaseRepository(ABC):
    """Base repository implementing common CRUD operations."""

    collection_name: str

    def __init__(self, database: str) -> None:
        self.database = database

    @property
    @abstractmethod
    def next_id_key(self) -> str:
        """Return the store key used to allocate identifiers."""

    @abstractmethod
    def create(self, **values: Any) -> dict[str, Any] | None:
        """Create and return a record."""

    def get(self, record_id: int) -> dict[str, Any] | None:
        with _storage_lock:
            for record in _read_store(self.database)[self.collection_name]:
                if record["id"] == record_id:
                    return record.copy()
        return None

    def list(self) -> list[dict[str, Any]]:
        with _storage_lock:
            return [
                record.copy()
                for record in _read_store(self.database)[self.collection_name]
            ]

    def update(self, record_id: int, **values: Any) -> dict[str, Any] | None:
        with _storage_lock:
            store = _read_store(self.database)
            for record in store[self.collection_name]:
                if record["id"] == record_id:
                    record.update(values)
                    _write_store(self.database, store)
                    return record.copy()
        return None

    def delete(self, record_id: int) -> bool:
        with _storage_lock:
            store = _read_store(self.database)
            records = store[self.collection_name]
            for index, record in enumerate(records):
                if record["id"] == record_id:
                    del records[index]
                    _write_store(self.database, store)
                    return True
        return False


class UserRepository(BaseRepository):
    """Repository for user records."""

    collection_name = "users"

    @property
    def next_id_key(self) -> str:
        return "next_user_id"

    def create(self, **values: Any) -> dict[str, Any] | None:
        username = values["username"]
        password_hash = generate_password_hash(values["password"], method="scrypt")
        with _storage_lock:
            store = _read_store(self.database)
            if any(user["username"] == username for user in store["users"]):
                return None
            user = {
                "id": store[self.next_id_key],
                "username": username,
                "password_hash": password_hash,
            }
            store[self.next_id_key] += 1
            store["users"].append(user)
            _write_store(self.database, store)
            return user.copy()

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with _storage_lock:
            for user in _read_store(self.database)["users"]:
                if user["username"] == username:
                    return user.copy()
        return None


class TaskRepository(BaseRepository):
    """Repository for owner-scoped task records."""

    collection_name = "tasks"

    def __init__(self, database: str, now: Callable[[], str]) -> None:
        super().__init__(database)
        self.now = now

    @property
    def next_id_key(self) -> str:
        return "next_id"

    def create(self, **values: Any) -> dict[str, Any]:
        with _storage_lock:
            store = _read_store(self.database)
            task = {
                "id": store[self.next_id_key],
                "title": values["title"],
                "status": "pending",
                "created_at": self.now(),
                "owner_id": values["owner_id"],
            }
            store[self.next_id_key] += 1
            store["tasks"].append(task)
            _write_store(self.database, store)
            return task.copy()

    def list_for_owner(self, owner_id: int) -> list[dict[str, Any]]:
        tasks = (
            task for task in self.list() if task.get("owner_id") == owner_id
        )
        return sorted(
            tasks,
            key=lambda task: (task["created_at"], task["id"]),
            reverse=True,
        )

    def paginate_for_owner(
        self, owner_id: int, *, cursor: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        tasks = self.list_for_owner(owner_id)
        start = 0
        if cursor is not None:
            start = next(
                (index + 1 for index, task in enumerate(tasks) if task["id"] == cursor),
                len(tasks),
            )

        page = tasks[start : start + limit]
        next_cursor = (
            str(page[-1]["id"]) if page and start + len(page) < len(tasks) else None
        )
        return page, next_cursor, len(tasks)

    def get_for_owner(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        task = self.get(task_id)
        if task is None or task.get("owner_id") != owner_id:
            return None
        return task

    def update_for_owner(
        self,
        task_id: int,
        owner_id: int,
        *,
        title: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        with _storage_lock:
            store = _read_store(self.database)
            for task in store["tasks"]:
                if task["id"] != task_id or task.get("owner_id") != owner_id:
                    continue
                if title is not None:
                    task["title"] = title
                if status is not None:
                    task["status"] = status
                _write_store(self.database, store)
                return task.copy()
        return None
