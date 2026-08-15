"""Repositories for the task-management application's persistent data."""

from abc import ABC, abstractmethod
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock


def _empty_store():
    return {"next_id": 1, "next_user_id": 1, "tasks": [], "users": []}


def _read_store(path):
    try:
        with path.open(encoding="utf-8") as file:
            store = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        store = _empty_store()
    store.setdefault("next_id", 1)
    store.setdefault("next_user_id", 1)
    store.setdefault("tasks", [])
    store.setdefault("users", [])
    for task in store["tasks"]:
        task.setdefault("owner_id", None)
    return store


def _write_store(path, store):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(store, file)
        file.write("\n")
        temporary_path = Path(file.name)
    temporary_path.replace(path)


def initialize_store(filename):
    """Create the store and apply the migration for pre-auth task records."""
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_store(path, _empty_store())
        return

    store = _read_store(path)
    store["next_user_id"] = max(
        store["next_user_id"],
        max((user.get("id", 0) for user in store["users"]), default=0) + 1,
    )
    _write_store(path, store)


class BaseRepository(ABC):
    """Provide common CRUD operations for a collection in the application store."""

    @property
    @abstractmethod
    def collection_name(self):
        """Return the store collection managed by this repository."""

    @property
    @abstractmethod
    def counter_name(self):
        """Return the store counter used to assign record IDs."""

    def __init__(self, filename, lock=None):
        self.path = Path(filename)
        self.lock = lock or Lock()

    def list(self):
        with self.lock:
            return list(_read_store(self.path)[self.collection_name])

    def get(self, record_id):
        with self.lock:
            return next(
                (record for record in _read_store(self.path)[self.collection_name]
                 if record.get("id") == record_id),
                None,
            )

    def create(self, record):
        with self.lock:
            store = _read_store(self.path)
            record = dict(record)
            record["id"] = store[self.counter_name]
            store[self.counter_name] += 1
            store[self.collection_name].append(record)
            _write_store(self.path, store)
            return record

    def update(self, record_id, changes):
        with self.lock:
            store = _read_store(self.path)
            record = next(
                (item for item in store[self.collection_name] if item.get("id") == record_id),
                None,
            )
            if record is None:
                return None
            record.update(changes)
            _write_store(self.path, store)
            return record

    def delete(self, record_id):
        with self.lock:
            store = _read_store(self.path)
            records = store[self.collection_name]
            record = next((item for item in records if item.get("id") == record_id), None)
            if record is None:
                return None
            records.remove(record)
            _write_store(self.path, store)
            return record


class TaskRepository(BaseRepository):
    collection_name = "tasks"
    counter_name = "next_id"

    def create_task(self, title, owner_id, created_at, status="pending"):
        return self.create({
            "title": title,
            "status": status,
            "created_at": created_at,
            "owner_id": owner_id,
        })

    def list_for_owner(self, owner_id):
        tasks = [task for task in self.list() if task.get("owner_id") == owner_id]
        tasks.sort(key=lambda task: (task["created_at"], task["id"]), reverse=True)
        return tasks

    def list_page_for_owner(self, owner_id, cursor=None, limit=20):
        tasks = self.list_for_owner(owner_id)
        start = 0
        if cursor is not None:
            cursor_index = next((index for index, task in enumerate(tasks)
                                 if task.get("id") == cursor), None)
            if cursor_index is None:
                return None, len(tasks), False
            start = cursor_index + 1
        page = tasks[start:start + limit + 1]
        return page[:limit], len(tasks), len(page) > limit

    def get_for_owner(self, task_id, owner_id):
        task = self.get(task_id)
        return task if task and task.get("owner_id") == owner_id else None

    def update_for_owner(self, task_id, owner_id, changes):
        task = self.get_for_owner(task_id, owner_id)
        if task is None:
            return None
        return self.update(task_id, changes)


class UserRepository(BaseRepository):
    collection_name = "users"
    counter_name = "next_user_id"

    def find_by_username(self, username):
        return next((user for user in self.list() if user["username"] == username), None)

    def find_by_id(self, user_id):
        return self.get(user_id)

    def create_user(self, username, password_hash, email=None):
        user = {"username": username, "password_hash": password_hash}
        if email:
            user["email"] = email
        return self.create(user)
