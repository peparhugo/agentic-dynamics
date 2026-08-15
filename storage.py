"""Flat-file (JSON) storage layer for tasks. No database engine is used —
all data lives in a single JSON file on disk, guarded by an in-process lock
plus atomic write-and-replace to avoid partial/corrupt writes."""

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
        _write({"next_id": 1, "tasks": []})


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


def create_task(title):
    with _lock:
        data = _read()
        task = {
            "id": data["next_id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        data["tasks"].append(task)
        data["next_id"] += 1
        _write(data)
        return task


def list_tasks():
    data = _read()
    return sorted(data["tasks"], key=lambda t: (t["created_at"], t["id"]), reverse=True)


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
