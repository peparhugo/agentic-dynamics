"""Repository layer for tasks and users.

Route handlers talk to these repositories instead of touching the storage
module's read/write primitives directly. storage.py remains the low-level
file I/O driver (locking, atomic read/write of the JSON document); this
module is where entity-specific CRUD logic lives.
"""

from abc import ABC, abstractmethod
from datetime import datetime

import storage


class BaseRepository(ABC):
    """Common CRUD contract shared by all repositories."""

    @abstractmethod
    def create(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, entity_id):
        raise NotImplementedError

    @abstractmethod
    def list_all(self, **filters):
        raise NotImplementedError

    @abstractmethod
    def update(self, entity_id, **kwargs):
        raise NotImplementedError


class TaskRepository(BaseRepository):
    def create(self, title, owner_id):
        with storage.lock:
            data = storage.read_data()
            task = {
                "id": data["next_id"],
                "title": title,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "owner_id": owner_id,
            }
            data["tasks"].append(task)
            data["next_id"] += 1
            storage.write_data(data)
            return task

    def get_by_id(self, task_id):
        data = storage.read_data()
        for task in data["tasks"]:
            if task["id"] == task_id:
                return task
        return None

    def list_all(self, owner_id=None):
        data = storage.read_data()
        tasks = [t for t in data["tasks"] if t.get("owner_id") == owner_id]
        return sorted(tasks, key=lambda t: (t["created_at"], t["id"]), reverse=True)

    def update(self, task_id, title=None, status=None):
        with storage.lock:
            data = storage.read_data()
            for task in data["tasks"]:
                if task["id"] == task_id:
                    if title is not None:
                        task["title"] = title
                    if status is not None:
                        task["status"] = status
                    storage.write_data(data)
                    return task
            return None


class UserRepository(BaseRepository):
    def create(self, username, password_hash):
        with storage.lock:
            data = storage.read_data()
            for user in data["users"]:
                if user["username"] == username:
                    return None
            user = {
                "id": data["next_user_id"],
                "username": username,
                "password_hash": password_hash,
            }
            data["users"].append(user)
            data["next_user_id"] += 1
            storage.write_data(data)
            return user

    def get_by_id(self, user_id):
        data = storage.read_data()
        for user in data["users"]:
            if user["id"] == user_id:
                return user
        return None

    def get_by_username(self, username):
        data = storage.read_data()
        for user in data["users"]:
            if user["username"] == username:
                return user
        return None

    def list_all(self):
        data = storage.read_data()
        return list(data["users"])

    def update(self, user_id, **fields):
        with storage.lock:
            data = storage.read_data()
            for user in data["users"]:
                if user["id"] == user_id:
                    user.update(fields)
                    storage.write_data(data)
                    return user
            return None
