"""A small Flask task-management API backed by a JSON flat file."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

from flask import Flask, jsonify, request


app = Flask(__name__)
app.config["TASKS_FILE"] = os.environ.get("TASKS_FILE", "tasks.json")

_storage_lock = Lock()


def _empty_store():
    return {"next_id": 1, "tasks": []}


def init_db():
    """Initialize the flat-file schema (retained as the startup hook name)."""
    path = Path(app.config["TASKS_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_store(_empty_store())


def _read_store():
    path = Path(app.config["TASKS_FILE"])
    try:
        with path.open(encoding="utf-8") as file:
            store = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        store = _empty_store()
    store.setdefault("next_id", 1)
    store.setdefault("tasks", [])
    return store


def _write_store(store):
    path = Path(app.config["TASKS_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace the file atomically so a request cannot observe a partial JSON file.
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(store, file)
        file.write("\n")
        temporary_path = Path(file.name)
    temporary_path.replace(path)


def _find_task(store, task_id):
    return next((task for task in store["tasks"] if task["id"] == task_id), None)


def _not_found():
    return jsonify({"error": "task not found"}), 404


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    with _storage_lock:
        store = _read_store()
        task = {
            "id": store["next_id"],
            "title": title.strip(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        store["next_id"] += 1
        store["tasks"].append(task)
        _write_store(store)
    return jsonify(task), 201


@app.get("/tasks")
def list_tasks():
    with _storage_lock:
        tasks = _read_store()["tasks"]
    tasks.sort(key=lambda task: (task["created_at"], task["id"]), reverse=True)
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
def get_task(task_id):
    with _storage_lock:
        task = _find_task(_read_store(), task_id)
    return jsonify(task) if task else _not_found()


@app.put("/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    with _storage_lock:
        store = _read_store()
        task = _find_task(store, task_id)
        if task is None:
            return _not_found()
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            task["title"] = data["title"].strip()
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            task["status"] = data["status"].strip()
        _write_store(store)
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run()
