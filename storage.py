"""Flat-file (JSON) storage driver for tasks and users. No database engine is
used — all data lives in a single JSON file on disk, guarded by an
in-process lock plus atomic write-and-replace to avoid partial/corrupt
writes.

This module only provides low-level file I/O primitives (locking, read,
write, migration-on-init). Entity-specific CRUD lives in repositories.py.
"""

import json
import os
import threading

lock = threading.Lock()

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
        write_data({"next_id": 1, "tasks": [], "next_user_id": 1, "users": []})
        return

    with lock:
        data = read_data()
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
            write_data(data)


def read_data():
    path = get_storage_file()
    with open(path, "r") as f:
        return json.load(f)


def write_data(data):
    path = get_storage_file()
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)
