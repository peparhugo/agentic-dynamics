"""Flask task-management API backed by a JSON flat file."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request


app = Flask(__name__)

# Kept as a module setting so deployments and tests can select their data file.
DATABASE = os.environ.get("TASKS_FILE", "tasks.json")
_storage_lock = Lock()


def _empty_store() -> dict:
    return {"next_id": 1, "tasks": []}


def init_db() -> None:
    """Initialize the flat-file schema if it does not already exist."""
    path = Path(DATABASE)
    with _storage_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            _write_store(_empty_store())


def _read_store() -> dict:
    path = Path(DATABASE)
    if not path.exists():
        return _empty_store()
    with path.open(encoding="utf-8") as data_file:
        return json.load(data_file)


def _write_store(store: dict) -> None:
    path = Path(DATABASE)
    temporary_path = path.with_name(f".{path.name}.tmp")
    with temporary_path.open("w", encoding="utf-8") as data_file:
        json.dump(store, data_file, indent=2)
        data_file.write("\n")
    os.replace(temporary_path, path)


def create_task(title: str) -> dict:
    with _storage_lock:
        store = _read_store()
        task = {
            "id": store["next_id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        store["next_id"] += 1
        store["tasks"].append(task)
        _write_store(store)
        return task.copy()


def get_tasks() -> list[dict]:
    with _storage_lock:
        tasks = _read_store()["tasks"]
        return sorted((task.copy() for task in tasks), key=lambda task: task["created_at"], reverse=True)


def get_task(task_id: int) -> dict | None:
    with _storage_lock:
        for task in _read_store()["tasks"]:
            if task["id"] == task_id:
                return task.copy()
    return None


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    with _storage_lock:
        store = _read_store()
        for task in store["tasks"]:
            if task["id"] != task_id:
                continue
            if title is not None:
                task["title"] = title
            if status is not None:
                task["status"] = status
            _write_store(store)
            return task.copy()
    return None


@app.get("/tasks")
def list_tasks():
    return jsonify(get_tasks())


@app.post("/tasks")
def add_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not data["title"].strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(data["title"].strip())), 201


@app.get("/tasks/<int:task_id>")
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
def edit_task(task_id: int):
    if get_task(task_id) is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object is required"}), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    title = data["title"].strip() if "title" in data else None
    task = update_task(task_id, title=title, status=data.get("status"))
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
