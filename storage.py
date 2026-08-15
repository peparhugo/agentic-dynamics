"""Flat-file (JSON) storage layer for tasks and users. No database engine is
used — all data lives in a single JSON file on disk, guarded by an
in-process lock plus atomic write-and-replace to avoid partial/corrupt
writes."""

import json
import os
import threading
from datetime import datetime

_lock = threading.Lock()

DEFAULT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "tasks.json"
)


def get_storage_file():
    return os.environ.get("TASKS_FILE", DEFAULT_FILE)


def init_storage():
    path = get_storage_file()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if not os.path.exists(path):
        _write({"next_id": 1, "tasks": [], "next_user_id": 1, "users": []})
        return

    with _lock:
        data = _read()
        changed = False
        if "users" not in data:
            data["users"] = []
            changed = True
        if "next_user_id" not in data:
            data["next_user_id"] = 1
            changed = True
        for task in data.get("tasks", []):
            if "owner_id" not in task:
                task["owner_id"] = None
                changed = True
        if changed:
            _write(data)


def _read():
    path = get_storage_file()
    with open(path, "r") as f:
        return json.load(f)


def _write(data):
    path = get_storage_file()
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def create_task(title, owner_id):
    with _lock:
        data = _read()
        task = {
            "id": data["next_id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "owner_id": owner_id,
        }
        data["tasks"].append(task)
        data["next_id"] += 1
        _write(data)
        return task


def list_tasks(owner_id):
    data = _read()
    tasks = [t for t in data["tasks"] if t.get("owner_id") == owner_id]
    return sorted(tasks, key=lambda t: (t["created_at"], t["id"]), reverse=True)


def get_task(task_id):
    data = _read()
    for task in data["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def update_task(task_id, title=None, status=None):
    with _lock:
        data = _read()
        for task in data["tasks"]:
            if task["id"] == task_id:
                if title is not None:
                    task["title"] = title
                if status is not None:
                    task["status"] = status
                _write(data)
                return task
        return None


def create_user(username, password_hash):
    with _lock:
        data = _read()
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
        _write(data)
        return user


def get_user_by_username(username):
    data = _read()
    for user in data["users"]:
        if user["username"] == username:
            return user
    return None


def get_user_by_id(user_id):
    data = _read()
    for user in data["users"]:
        if user["id"] == user_id:
            return user
    return None
