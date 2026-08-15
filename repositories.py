"""Repositories for the application's JSON-backed persistence store."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from threading import Lock
from typing import Any


StorageData = dict[str, list[dict[str, Any]]]


class BaseRepository(ABC):
    """Provides common CRUD operations for a collection in the data store."""

    def __init__(
        self,
        read_data: Callable[[], StorageData],
        write_data: Callable[[StorageData], None],
        storage_lock: Lock,
    ) -> None:
        self._read_data = read_data
        self._write_data = write_data
        self._storage_lock = storage_lock

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """The top-level collection managed by this repository."""

    def get_all(self) -> list[dict[str, Any]]:
        with self._storage_lock:
            return self._read_data()[self.collection_name]

    def get_by_id(self, entity_id: int) -> dict[str, Any] | None:
        with self._storage_lock:
            return self._find_by_id(self._read_data()[self.collection_name], entity_id)

    def create(self, attributes: dict[str, Any]) -> dict[str, Any]:
        with self._storage_lock:
            data = self._read_data()
            collection = data[self.collection_name]
            entity = {
                "id": max((item.get("id", 0) for item in collection), default=0) + 1,
                **attributes,
            }
            collection.append(entity)
            self._write_data(data)
            return entity

    def update(self, entity_id: int, attributes: dict[str, Any]) -> dict[str, Any] | None:
        with self._storage_lock:
            data = self._read_data()
            entity = self._find_by_id(data[self.collection_name], entity_id)
            if entity is None:
                return None
            entity.update(attributes)
            self._write_data(data)
            return entity

    def delete(self, entity_id: int) -> bool:
        with self._storage_lock:
            data = self._read_data()
            collection = data[self.collection_name]
            entity = self._find_by_id(collection, entity_id)
            if entity is None:
                return False
            collection.remove(entity)
            self._write_data(data)
            return True

    @staticmethod
    def _find_by_id(collection: list[dict[str, Any]], entity_id: int) -> dict[str, Any] | None:
        return next((item for item in collection if item.get("id") == entity_id), None)


class TaskRepository(BaseRepository):
    @property
    def collection_name(self) -> str:
        return "tasks"

    def list_for_owner(self, owner_id: int) -> list[dict[str, Any]]:
        return [task for task in self.get_all() if task.get("owner_id") == owner_id]

    def list_page_for_owner(
        self, owner_id: int, cursor_id: int | None, limit: int
    ) -> tuple[list[dict[str, Any]] | None, str | None, int]:
        """Return a stable newest-first page, starting after ``cursor_id``."""
        tasks = sorted(
            self.list_for_owner(owner_id), key=lambda task: task["created_at"], reverse=True
        )
        total = len(tasks)
        start = 0
        if cursor_id is not None:
            cursor_index = next(
                (index for index, task in enumerate(tasks) if task.get("id") == cursor_id), None
            )
            if cursor_index is None:
                return None, None, total
            start = cursor_index + 1
        page = tasks[start : start + limit]
        next_cursor = str(page[-1]["id"]) if start + limit < total else None
        return page, next_cursor, total

    def get_for_owner(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        with self._storage_lock:
            task = self._find_by_id(self._read_data()[self.collection_name], task_id)
            return task if task is not None and task.get("owner_id") == owner_id else None

    def update_for_owner(
        self, task_id: int, owner_id: int, attributes: dict[str, Any]
    ) -> tuple[dict[str, Any], bool] | None:
        with self._storage_lock:
            data = self._read_data()
            task = self._find_by_id(data[self.collection_name], task_id)
            if task is None or task.get("owner_id") != owner_id:
                return None
            was_completed = task.get("status") == "completed"
            task.update(attributes)
            self._write_data(data)
            return task, was_completed


class UserRepository(BaseRepository):
    @property
    def collection_name(self) -> str:
        return "users"

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with self._storage_lock:
            return next(
                (user for user in self._read_data()[self.collection_name] if user.get("username") == username),
                None,
            )

    def create_if_username_available(self, attributes: dict[str, Any]) -> dict[str, Any] | None:
        with self._storage_lock:
            data = self._read_data()
            users = data[self.collection_name]
            if any(user.get("username") == attributes["username"] for user in users):
                return None
            user = {
                "id": max((item.get("id", 0) for item in users), default=0) + 1,
                **attributes,
            }
            users.append(user)
            self._write_data(data)
            return user
