"""Repository abstractions for the application's persistent data."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Generic, TypeVar

from werkzeug.security import generate_password_hash


@dataclass
class User:
    id: int
    username: str
    password_hash: str


@dataclass
class Task:
    id: int
    title: str
    status: str
    created_at: str
    owner_id: int | None


Entity = TypeVar("Entity")


class BaseRepository(ABC, Generic[Entity]):
    """Define the CRUD contract shared by all repositories."""

    def __init__(self, store: Callable[[], dict[str, Any]], lock: Lock) -> None:
        self._store = store
        self._lock = lock

    @abstractmethod
    def create(self, *args: Any, **kwargs: Any) -> Entity | None:
        """Create and return an entity."""

    @abstractmethod
    def get_by_id(self, entity_id: int) -> Entity | None:
        """Return an entity by its identifier."""

    @abstractmethod
    def get_all(self) -> list[Entity]:
        """Return all entities."""

    @abstractmethod
    def update(self, entity_id: int, **changes: Any) -> Entity | None:
        """Update and return an entity."""

    @abstractmethod
    def delete(self, entity_id: int) -> bool:
        """Delete an entity and report whether it existed."""


class UserRepository(BaseRepository[User]):
    def create(self, username: str, password: str) -> User | None:
        with self._lock:
            store = self._store()
            if any(user["username"] == username for user in store["users"]):
                return None
            user = User(
                id=store["next_user_id"],
                username=username,
                password_hash=generate_password_hash(password),
            )
            store["next_user_id"] += 1
            store["users"].append(asdict(user))
            return user

    def get_by_id(self, entity_id: int) -> User | None:
        with self._lock:
            for user in self._store()["users"]:
                if user["id"] == entity_id:
                    return User(**user)
        return None

    def get_by_username(self, username: str) -> User | None:
        with self._lock:
            for user in self._store()["users"]:
                if user["username"] == username:
                    return User(**user)
        return None

    def get_all(self) -> list[User]:
        with self._lock:
            return [User(**user) for user in self._store()["users"]]

    def update(self, entity_id: int, **changes: Any) -> User | None:
        with self._lock:
            for user in self._store()["users"]:
                if user["id"] != entity_id:
                    continue
                if "username" in changes:
                    user["username"] = changes["username"]
                if "password" in changes:
                    user["password_hash"] = generate_password_hash(changes["password"])
                return User(**user)
        return None

    def delete(self, entity_id: int) -> bool:
        with self._lock:
            users = self._store()["users"]
            for index, user in enumerate(users):
                if user["id"] == entity_id:
                    del users[index]
                    return True
        return False


class TaskRepository(BaseRepository[dict[str, Any]]):
    def create(self, title: str, owner_id: int | None = None) -> dict[str, Any]:
        with self._lock:
            store = self._store()
            task = Task(
                id=store["next_task_id"],
                title=title,
                status="pending",
                created_at=datetime.now(timezone.utc).isoformat(),
                owner_id=owner_id,
            )
            store["next_task_id"] += 1
            stored_task = asdict(task)
            store["tasks"].append(stored_task)
            return stored_task.copy()

    def get_by_id(
        self, entity_id: int, owner_id: int | None = None
    ) -> dict[str, Any] | None:
        with self._lock:
            for task in self._store()["tasks"]:
                if task["id"] == entity_id and (
                    owner_id is None or task["owner_id"] == owner_id
                ):
                    return task.copy()
        return None

    def get_all(self, owner_id: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            tasks = self._ordered_tasks(owner_id)
            return [task.copy() for task in tasks]

    def paginate(
        self, owner_id: int, cursor: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], int | None, int]:
        with self._lock:
            tasks = self._ordered_tasks(owner_id)
            start = 0
            if cursor is not None:
                try:
                    start = next(
                        index + 1
                        for index, task in enumerate(tasks)
                        if task["id"] == cursor
                    )
                except StopIteration as error:
                    raise ValueError("invalid cursor") from error

            page = tasks[start : start + limit]
            next_cursor = page[-1]["id"] if start + len(page) < len(tasks) else None
            return [task.copy() for task in page], next_cursor, len(tasks)

    def _ordered_tasks(self, owner_id: int | None) -> list[dict[str, Any]]:
        tasks = [
            task
            for task in self._store()["tasks"]
            if owner_id is None or task["owner_id"] == owner_id
        ]
        tasks.sort(key=lambda task: (task["created_at"], task["id"]), reverse=True)
        return tasks

    def update(
        self, entity_id: int, owner_id: int | None = None, **changes: Any
    ) -> dict[str, Any] | None:
        with self._lock:
            for task in self._store()["tasks"]:
                if task["id"] != entity_id or (
                    owner_id is not None and task["owner_id"] != owner_id
                ):
                    continue
                if changes.get("title") is not None:
                    task["title"] = changes["title"]
                if changes.get("status") is not None:
                    task["status"] = changes["status"]
                return task.copy()
        return None

    def delete(self, entity_id: int, owner_id: int | None = None) -> bool:
        with self._lock:
            tasks = self._store()["tasks"]
            for index, task in enumerate(tasks):
                if task["id"] == entity_id and (
                    owner_id is None or task["owner_id"] == owner_id
                ):
                    del tasks[index]
                    return True
        return False
