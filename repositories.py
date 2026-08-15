import abc
import json
import os
import threading

storage_lock = threading.RLock()


class BaseRepository(abc.ABC):
    def __init__(self, path_provider):
        self._path_provider = path_provider

    @property
    def path(self):
        return self._path_provider()

    def _read(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return json.load(f)

    def _write(self, items):
        with open(self.path, "w") as f:
            json.dump(items, f)

    def ensure_exists(self):
        with storage_lock:
            if not os.path.exists(self.path):
                self._write([])

    def all(self):
        with storage_lock:
            return self._read()

    def get(self, item_id):
        with storage_lock:
            return next(
                (item for item in self._read() if item.get("id") == item_id),
                None,
            )

    def next_id(self):
        with storage_lock:
            items = self._read()
            return max((item["id"] for item in items), default=0) + 1

    def create(self, **fields):
        with storage_lock:
            items = self._read()
            item = dict(fields)
            item["id"] = max((item["id"] for item in items), default=0) + 1
            items.append(item)
            self._write(items)
            return item

    def save(self, item):
        with storage_lock:
            items = self._read()
            for index, existing in enumerate(items):
                if existing.get("id") == item.get("id"):
                    items[index] = item
                    break
            else:
                items.append(item)
            self._write(items)
            return item

    def save_all(self, items):
        with storage_lock:
            self._write(items)


class TaskRepository(BaseRepository):
    def find_by_owner(self, owner_id):
        return [task for task in self.all() if task.get("owner_id") == owner_id]


class UserRepository(BaseRepository):
    def find_by_username(self, username):
        with storage_lock:
            return next(
                (user for user in self._read() if user.get("username") == username),
                None,
            )
