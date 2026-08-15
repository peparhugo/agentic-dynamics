"""
Repository pattern for the Todo API data layer.

All access to the underlying storage (a JSON flat file) happens through
repository classes. Route handlers never touch storage directly.
"""

import json
import os
import threading
from abc import ABC, abstractmethod
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash


class BaseRepository(ABC):
    """Abstract base repository providing common CRUD operations."""

    def __init__(self, data_file=None, lock=None):
        if callable(data_file):
            self._data_file_provider = data_file
        else:
            path = data_file or os.environ.get("DATA_FILE", "tasks.json")
            self._data_file_provider = lambda: path
        self._lock = lock if lock is not None else threading.Lock()

    def _data_file(self) -> str:
        return self._data_file_provider()

    def read_store(self) -> dict:
        with open(self._data_file()) as f:
            return json.load(f)

    def write_store(self, store: dict) -> None:
        with open(self._data_file(), "w") as f:
            json.dump(store, f, indent=2)

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """Collection name within the store."""

    @property
    @abstractmethod
    def next_id_key(self) -> str:
        """Store key tracking the next id for this entity."""

    def get(self, entity_id: int) -> dict | None:
        store = self.read_store()
        for item in store.get(self.entity_name, []):
            if item["id"] == entity_id:
                return item
        return None

    def all(self) -> list:
        store = self.read_store()
        return store.get(self.entity_name, [])

    def create(self, item: dict, conflict_checker=None) -> dict | None:
        with self._lock:
            store = self.read_store()
            if conflict_checker is not None and conflict_checker(store, item):
                return None
            item["id"] = store[self.next_id_key]
            store[self.entity_name].append(item)
            store[self.next_id_key] += 1
            self.write_store(store)
            return item


class TaskRepository(BaseRepository):
    """Persistence for tasks, scoped by owner."""

    @property
    def entity_name(self) -> str:
        return "tasks"

    @property
    def next_id_key(self) -> str:
        return "next_id"

    def create_task(self, title: str, owner_id: int) -> dict:
        task = {
            "title": title,
            "status": "pending",
            "owner_id": owner_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        return self.create(task)

    def list_for_owner(self, owner_id: int) -> list:
        store = self.read_store()
        mine = [t for t in store["tasks"] if t.get("owner_id") == owner_id]
        return sorted(mine, key=lambda t: t["created_at"], reverse=True)

    def get_for_owner(self, task_id: int, owner_id: int) -> dict | None:
        store = self.read_store()
        for task in store["tasks"]:
            if task["id"] == task_id and task.get("owner_id") == owner_id:
                return task
        return None

    def update(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        with self._lock:
            store = self.read_store()
            for task in store["tasks"]:
                if task["id"] == task_id and task.get("owner_id") == owner_id:
                    if title is not None:
                        task["title"] = title
                    if status is not None:
                        task["status"] = status
                    self.write_store(store)
                    return task
        return None


class UserRepository(BaseRepository):
    """Persistence for users and authentication lookups."""

    @property
    def entity_name(self) -> str:
        return "users"

    @property
    def next_id_key(self) -> str:
        return "next_user_id"

    def create_user(self, username: str, password: str, email: str | None = None) -> dict | None:
        user = {
            "username": username,
            "email": email or f"{username}@example.com",
            "password_hash": generate_password_hash(password),
        }
        return self.create(
            user,
            conflict_checker=lambda store, item: any(
                u["username"] == item["username"] for u in store["users"]
            ),
        )

    def get_by_username(self, username: str) -> dict | None:
        store = self.read_store()
        for user in store["users"]:
            if user["username"] == username:
                return user
        return None

    def verify_user(self, username: str, password: str) -> dict | None:
        user = self.get_by_username(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            return None
        return user
