import json
import os
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


_storage_lock = threading.RLock()


class BaseRepository(ABC):
    """File-backed repository with common CRUD operations."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        self._initialize()

    @property
    @abstractmethod
    def entity_name(self) -> str:
        """Human-readable entity name used in storage errors."""

    def _initialize(self) -> None:
        with _storage_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self.path.write_text("[]\n", encoding="utf-8")

    def _read(self) -> list[dict[str, Any]]:
        self._initialize()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError(f"{self.entity_name} storage could not be read") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"{self.entity_name} storage has an invalid format")
        return data

    def _write(self, records: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temporary_file:
                json.dump(records, temporary_file, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def get_all(self) -> list[dict[str, Any]]:
        with _storage_lock:
            return [record.copy() for record in self._read()]

    def get_by_id(self, record_id: int) -> dict[str, Any] | None:
        with _storage_lock:
            record = next(
                (record for record in self._read() if record["id"] == record_id),
                None,
            )
            return record.copy() if record is not None else None

    def create(self, attributes: dict[str, Any]) -> dict[str, Any]:
        with _storage_lock:
            records = self._read()
            record = {
                **attributes,
                "id": max((item["id"] for item in records), default=0) + 1,
            }
            records.append(record)
            self._write(records)
            return record.copy()

    def update(
        self, record_id: int, attributes: dict[str, Any]
    ) -> dict[str, Any] | None:
        with _storage_lock:
            records = self._read()
            record = next(
                (record for record in records if record["id"] == record_id), None
            )
            if record is None:
                return None
            record.update(attributes)
            self._write(records)
            return record.copy()

    def delete(self, record_id: int) -> bool:
        with _storage_lock:
            records = self._read()
            remaining = [record for record in records if record["id"] != record_id]
            if len(remaining) == len(records):
                return False
            self._write(remaining)
            return True


class TaskRepository(BaseRepository):
    @property
    def entity_name(self) -> str:
        return "Task"

    def __init__(self, path: str | os.PathLike[str]) -> None:
        super().__init__(path)
        self._migrate_legacy_tasks()

    def _migrate_legacy_tasks(self) -> None:
        with _storage_lock:
            tasks = self._read()
            migrated = False
            for task in tasks:
                if "owner_id" not in task:
                    task["owner_id"] = None
                    migrated = True
            if migrated:
                self._write(tasks)

    def create_for_owner(
        self, title: str, owner_id: int, created_at: str
    ) -> dict[str, Any]:
        return self.create(
            {
                "title": title,
                "status": "pending",
                "created_at": created_at,
                "owner_id": owner_id,
            }
        )

    def list_for_owner(self, owner_id: int) -> list[dict[str, Any]]:
        tasks = [
            task for task in self.get_all() if task.get("owner_id") == owner_id
        ]
        return sorted(tasks, key=lambda task: task["id"], reverse=True)

    def paginate_for_owner(
        self, owner_id: int, cursor: int | None, limit: int
    ) -> tuple[list[dict[str, Any]], str | None, int]:
        tasks = self.list_for_owner(owner_id)
        total = len(tasks)
        if cursor is not None:
            tasks = [task for task in tasks if task["id"] < cursor]

        page = tasks[:limit]
        next_cursor = str(page[-1]["id"]) if len(tasks) > limit else None
        return page, next_cursor, total

    def get_for_owner(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        task = self.get_by_id(task_id)
        if task is None or task.get("owner_id") != owner_id:
            return None
        return task

    def update_for_owner(
        self, task_id: int, owner_id: int, attributes: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        with _storage_lock:
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
            previous = task.copy()
            task.update(attributes)
            self._write(tasks)
            return task.copy(), previous


class UserRepository(BaseRepository):
    @property
    def entity_name(self) -> str:
        return "User"

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with _storage_lock:
            user = next(
                (user for user in self._read() if user["username"] == username),
                None,
            )
            return user.copy() if user is not None else None

    def create_user(
        self, username: str, email: str, password_hash: str
    ) -> dict[str, Any] | None:
        with _storage_lock:
            users = self._read()
            if any(user["username"] == username for user in users):
                return None
            user = {
                "id": max((item["id"] for item in users), default=0) + 1,
                "username": username,
                "email": email,
                "password_hash": password_hash,
            }
            users.append(user)
            self._write(users)
            return user.copy()


def init_storage(
    tasks_path: str | os.PathLike[str], users_path: str | os.PathLike[str]
) -> tuple[TaskRepository, UserRepository]:
    """Initialize application storage and return its repositories."""
    return TaskRepository(tasks_path), UserRepository(users_path)
