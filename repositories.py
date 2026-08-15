"""Repositories for the task-management JSON data store."""

from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Callable


class BaseRepository(ABC):
    """Provides common CRUD operations for entities in the flat-file store."""

    def __init__(self, database_path: Callable[[], str]):
        self._database_path = database_path

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """The collection name used in the store."""

    @property
    @abstractmethod
    def id_counter_name(self) -> str:
        """The store field containing the next entity identifier."""

    def initialize(self) -> None:
        """Create the store and migrate its shared schema when needed."""
        path = Path(self._database_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.stat().st_size == 0:
            self._write_store({"next_id": 1, "next_user_id": 1, "tasks": [], "users": []})
            return

        with path.open(encoding="utf-8") as data_file:
            store = json.load(data_file)
        changed = False
        if "users" not in store:
            store["users"] = []
            changed = True
        if "next_user_id" not in store:
            store["next_user_id"] = max((user["id"] for user in store["users"]), default=0) + 1
            changed = True
        for task in store.get("tasks", []):
            if "owner_id" not in task:
                task["owner_id"] = None
                changed = True
        if changed:
            self._write_store(store)

    def create(self, entity: dict) -> dict:
        store = self._read_store()
        entity = {"id": store[self.id_counter_name], **entity}
        store[self.id_counter_name] += 1
        store[self.entity_name].append(entity)
        self._write_store(store)
        return entity

    def list(self) -> list[dict]:
        return self._read_store()[self.entity_name]

    def get_by_id(self, entity_id: int) -> dict | None:
        return next((entity for entity in self.list() if entity["id"] == entity_id), None)

    def update(self, entity_id: int, changes: dict) -> dict | None:
        store = self._read_store()
        for entity in store[self.entity_name]:
            if entity["id"] == entity_id:
                entity.update(changes)
                self._write_store(store)
                return entity
        return None

    def _read_store(self) -> dict:
        self.initialize()
        with Path(self._database_path()).open(encoding="utf-8") as data_file:
            return json.load(data_file)

    def _write_store(self, store: dict) -> None:
        path = Path(self._database_path())
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        with temporary_path.open("w", encoding="utf-8") as data_file:
            json.dump(store, data_file)
        temporary_path.replace(path)


class TaskRepository(BaseRepository):
    @property
    def entity_name(self) -> str:
        return "tasks"

    @property
    def id_counter_name(self) -> str:
        return "next_id"

    def list_for_owner(self, owner_id: int) -> list[dict]:
        tasks = [task for task in self.list() if task["owner_id"] == owner_id]
        return sorted(tasks, key=lambda task: task["created_at"], reverse=True)

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        task = self.get_by_id(task_id)
        return task if task is not None and task["owner_id"] == owner_id else None

    def update_for_owner(self, task_id: int, owner_id: int, changes: dict) -> dict | None:
        task = self.get_for_owner(task_id, owner_id)
        return self.update(task_id, changes) if task is not None else None


class UserRepository(BaseRepository):
    @property
    def entity_name(self) -> str:
        return "users"

    @property
    def id_counter_name(self) -> str:
        return "next_user_id"

    def get_by_username(self, username: str) -> dict | None:
        return next((user for user in self.list() if user["username"] == username), None)
