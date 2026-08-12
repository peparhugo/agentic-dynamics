"""
Repository-pattern data access layer for the task management API.

All flat-file storage operations live here. Route handlers interact with
repository instances instead of touching the store directly.
"""

import json
import os
import threading
from abc import ABC, abstractmethod
from datetime import datetime

from werkzeug.security import generate_password_hash


class BaseRepository(ABC):
    """Common CRUD operations backed by the flat-file store.

    Subclasses specialise the generic operations for a single collection
    (``tasks`` or ``users``) while sharing the same store plumbing.
    """

    _lock = threading.RLock()
    _collection = None

    def __init__(self, data_file_getter=None):
        self._data_file_getter = data_file_getter or (lambda: "tasks.json")

    @property
    def _data_file(self) -> str:
        return self._data_file_getter()

    # ── store plumbing ─────────────────────────────────────────

    def _empty_store(self) -> dict:
        return {"tasks": [], "users": [], "next_id": 1}

    def _migrate(self, data: dict) -> tuple[dict, bool]:
        """Bring an existing flat-file store up to the current schema.

        Returns ``(data, changed)`` where ``changed`` is True when the
        store was modified and should be written back to disk.
        """
        changed = False
        if not isinstance(data, dict):
            data = {}
            changed = True
        if "tasks" not in data:
            data["tasks"] = []
            changed = True
        if "users" not in data:
            data["users"] = []
            changed = True
        if "next_id" not in data or not isinstance(data["next_id"], int):
            data["next_id"] = 1
            changed = True
        for task in data["tasks"]:
            if not isinstance(task, dict):
                continue
            if "owner_id" not in task:
                task["owner_id"] = None
                changed = True
        return data, changed

    def _read_store(self) -> dict:
        with self._lock:
            try:
                with open(self._data_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except FileNotFoundError:
                data = self._empty_store()
                self._write_store(data)
                return data
            except (json.JSONDecodeError, ValueError):
                data = self._empty_store()
            data, changed = self._migrate(data)
            if changed:
                self._write_store(data)
            return data

    def _write_store(self, data: dict) -> None:
        tmp = self._data_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, self._data_file)

    # ── abstract CRUD ──────────────────────────────────────────

    @abstractmethod
    def get(self, entity_id):
        """Return a single entity by id, or None if it does not exist."""

    @abstractmethod
    def list(self, **filters):
        """Return entities matching the given filters."""

    @abstractmethod
    def create(self, **fields):
        """Persist a new entity and return it."""

    @abstractmethod
    def update(self, entity_id, **fields):
        """Update an entity by id and return it, or None if missing."""

    @abstractmethod
    def delete(self, entity_id):
        """Delete an entity by id and return it, or None if missing."""


class TaskRepository(BaseRepository):
    """CRUD operations for the ``tasks`` collection."""

    _collection = "tasks"

    def get(self, task_id: int, owner_id: int | None = None) -> dict | None:
        data = self._read_store()
        for task in data[self._collection]:
            if task["id"] == task_id and (
                owner_id is None or task.get("owner_id") == owner_id
            ):
                return task
        return None

    def list(self, owner_id: int | None = None) -> list[dict]:
        data = self._read_store()
        tasks = [
            task
            for task in data[self._collection]
            if owner_id is None or task.get("owner_id") == owner_id
        ]
        return sorted(tasks, key=lambda task: task["created_at"], reverse=True)

    def list_page(
        self,
        owner_id: int | None = None,
        cursor: int | None = None,
        limit: int = 20,
    ) -> "tuple[list[dict], int, int]":
        """Return a cursor-based page of tasks for an owner.

        Returns ``(page, total, start)`` where ``page`` contains at most
        ``limit`` tasks ordered by id descending, ``total`` is the number of
        matching tasks for the owner, and ``start`` is the index of the first
        item in ``page`` within the full ordering (used to decide whether more
        pages exist).
        """
        data = self._read_store()
        tasks = [
            task
            for task in data[self._collection]
            if owner_id is None or task.get("owner_id") == owner_id
        ]
        tasks.sort(key=lambda task: task["id"], reverse=True)
        total = len(tasks)

        start = 0
        if cursor is not None:
            for index, task in enumerate(tasks):
                if task["id"] < cursor:
                    start = index
                    break
            else:
                start = total

        page = tasks[start : start + limit]
        return page, total, start

    def create(self, title: str, owner_id: int) -> dict:
        with self._lock:
            data = self._read_store()
            task = {
                "id": data["next_id"],
                "title": title,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "owner_id": owner_id,
            }
            data[self._collection].append(task)
            data["next_id"] += 1
            self._write_store(data)
            return task

    def update(
        self,
        task_id: int,
        owner_id: int,
        title: str | None = None,
        status: str | None = None,
    ) -> dict | None:
        with self._lock:
            data = self._read_store()
            for task in data[self._collection]:
                if task["id"] == task_id and task.get("owner_id") == owner_id:
                    if title is not None:
                        task["title"] = title
                    if status is not None:
                        task["status"] = status
                    self._write_store(data)
                    return task
            return None

    def delete(self, task_id: int, owner_id: int | None = None) -> dict | None:
        with self._lock:
            data = self._read_store()
            collection = data[self._collection]
            for index, task in enumerate(collection):
                if task["id"] == task_id and (
                    owner_id is None or task.get("owner_id") == owner_id
                ):
                    del collection[index]
                    self._write_store(data)
                    return task
            return None


class UserRepository(BaseRepository):
    """CRUD operations for the ``users`` collection."""

    _collection = "users"

    def get(self, user_id: int) -> dict | None:
        data = self._read_store()
        for user in data[self._collection]:
            if user["id"] == user_id:
                return user
        return None

    def get_by_username(self, username: str) -> dict | None:
        data = self._read_store()
        for user in data[self._collection]:
            if user["username"] == username:
                return user
        return None

    def list(self, **filters) -> list[dict]:
        data = self._read_store()
        return list(data[self._collection])

    def create(self, username: str, password: str) -> dict:
        with self._lock:
            data = self._read_store()
            if any(u["username"] == username for u in data[self._collection]):
                raise ValueError("username already taken")
            user = {
                "id": len(data[self._collection]) + 1,
                "username": username,
                "password_hash": generate_password_hash(password),
            }
            data[self._collection].append(user)
            self._write_store(data)
            return {"id": user["id"], "username": user["username"]}

    def update(self, user_id: int, **fields) -> dict | None:
        with self._lock:
            data = self._read_store()
            for user in data[self._collection]:
                if user["id"] == user_id:
                    for key, value in fields.items():
                        user[key] = value
                    self._write_store(data)
                    return user
            return None

    def delete(self, user_id: int) -> dict | None:
        with self._lock:
            data = self._read_store()
            collection = data[self._collection]
            for index, user in enumerate(collection):
                if user["id"] == user_id:
                    del collection[index]
                    self._write_store(data)
                    return user
            return None

    def get_email(self, user_id: int) -> str | None:
        """Resolve an owner's email address (falling back to a derived address)."""
        user = self.get(user_id)
        if user is None:
            return None
        return user.get("email") or f"{user['username']}@example.com"
