"""Repositories for the application's persistent data."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from threading import Lock


class BaseRepository(ABC):
    """Common CRUD operations for collections in the application store."""

    collection_name = None
    id_counter_name = None

    def __init__(self, data_file, file_lock=None):
        self.data_file = Path(data_file)
        self.file_lock = file_lock or Lock()

    @abstractmethod
    def _collection_defaults(self):
        """Return fields required when an old store is migrated."""

    def initialize(self):
        with self.file_lock:
            self._read_data()

    def _read_data(self):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self._write_data({"next_id": 1, "next_user_id": 1, "users": [], "tasks": []})
        try:
            with self.data_file.open("r", encoding="utf-8") as data_file:
                data = json.load(data_file)
        except (OSError, json.JSONDecodeError):
            data = {"next_id": 1, "tasks": []}

        migrated = False
        for key, default in {
            "next_id": 1,
            "next_user_id": 1,
            "users": [],
            "tasks": [],
        }.items():
            if key not in data:
                data[key] = default
                migrated = True
        for task in data["tasks"]:
            if "owner_id" not in task:
                task["owner_id"] = None
                migrated = True
        if migrated:
            self._write_data(data)
        return data

    def _write_data(self, data):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_name = tempfile.mkstemp(
            dir=self.data_file.parent, prefix=f".{self.data_file.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
                json.dump(data, temporary_file, indent=2)
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, self.data_file)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def create(self, values):
        with self.file_lock:
            data = self._read_data()
            record = dict(values)
            record["id"] = data[self.id_counter_name]
            data[self.id_counter_name] += 1
            data[self.collection_name].append(record)
            self._write_data(data)
            return record

    def get(self, record_id):
        with self.file_lock:
            return next((record for record in self._read_data()[self.collection_name]
                         if record["id"] == record_id), None)

    def list(self):
        with self.file_lock:
            return list(self._read_data()[self.collection_name])

    def update(self, record_id, values):
        with self.file_lock:
            data = self._read_data()
            record = next((item for item in data[self.collection_name] if item["id"] == record_id), None)
            if record is None:
                return None
            record.update(values)
            self._write_data(data)
            return record

    def delete(self, record_id):
        with self.file_lock:
            data = self._read_data()
            records = data[self.collection_name]
            record = next((item for item in records if item["id"] == record_id), None)
            if record is None:
                return None
            records.remove(record)
            self._write_data(data)
            return record


class UserRepository(BaseRepository):
    collection_name = "users"
    id_counter_name = "next_user_id"

    def _collection_defaults(self):
        return {"users": [], "next_user_id": 1}

    def find_by_username(self, username):
        with self.file_lock:
            return next((user for user in self._read_data()[self.collection_name]
                         if user["username"] == username), None)


class TaskRepository(BaseRepository):
    collection_name = "tasks"
    id_counter_name = "next_id"

    def _collection_defaults(self):
        return {"tasks": [], "next_id": 1}

    def create_for_user(self, title, owner_id):
        return self.create({
            "title": title,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": owner_id,
        })

    def list_for_user(self, owner_id):
        tasks = [task for task in self.list() if task.get("owner_id") == owner_id]
        return sorted(tasks, key=lambda task: (task.get("created_at", ""), task.get("id", 0)), reverse=True)

    def paginate_for_user(self, owner_id, cursor=None, limit=20):
        tasks = self.list_for_user(owner_id)
        start = 0
        if cursor is not None:
            cursor_index = next((index for index, task in enumerate(tasks) if task["id"] == cursor), None)
            if cursor_index is None:
                return None, len(tasks), None
            start = cursor_index + 1
        page = tasks[start:start + limit]
        next_cursor = str(page[-1]["id"]) if start + len(page) < len(tasks) else None
        return page, len(tasks), next_cursor

    def get_for_user(self, task_id, owner_id):
        task = self.get(task_id)
        return task if task is not None and task.get("owner_id") == owner_id else None

    def update_for_user(self, task_id, owner_id, values):
        task = self.get_for_user(task_id, owner_id)
        if task is None:
            return None
        previous_status = task.get("status")
        updated = self.update(task_id, values)
        return updated, previous_status
