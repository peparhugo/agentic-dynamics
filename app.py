"""Flat-file Flask API for managing tasks."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from threading import Lock

from flask import Flask, jsonify, request


app = Flask(__name__)
app.config["TASKS_FILE"] = os.environ.get("TASKS_FILE", "tasks.json")
_storage_lock = Lock()


def _storage_path() -> Path:
    return Path(app.config["TASKS_FILE"])


def init_storage() -> None:
    """Create the JSON data file with its initial schema when needed."""
    path = _storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_tasks([])


def _read_tasks() -> list[dict]:
    path = _storage_path()
    if not path.exists():
        init_storage()
    try:
        with path.open(encoding="utf-8") as data_file:
            tasks = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        return []
    return tasks if isinstance(tasks, list) else []


def _write_tasks(tasks: list[dict]) -> None:
    path = _storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(tasks, temporary_file, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        os.unlink(temporary_name)
        raise


def _task_or_404(task_id: int, tasks: list[dict]):
    task = next((task for task in tasks if task["id"] == task_id), None)
    if task is None:
        return None, (jsonify(error="task not found"), 404)
    return task, None


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@app.post("/tasks")
def create_task():
    data = _json_body()
    title = data.get("title") if data else None
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400

    with _storage_lock:
        tasks = _read_tasks()
        task = {
            "id": max((item["id"] for item in tasks), default=0) + 1,
            "title": title.strip(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tasks.append(task)
        _write_tasks(tasks)
    return jsonify(task), 201


@app.get("/tasks")
def list_tasks():
    with _storage_lock:
        tasks = _read_tasks()
    return jsonify(sorted(tasks, key=lambda task: task["created_at"], reverse=True))


@app.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    with _storage_lock:
        task, error = _task_or_404(task_id, _read_tasks())
    return error if error else jsonify(task)


@app.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    data = _json_body()
    if data is None or not any(field in data for field in ("title", "status")):
        return jsonify(error="title or status is required"), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify(error="title must be a non-empty string"), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify(error="status must be a string"), 400

    with _storage_lock:
        tasks = _read_tasks()
        task, error = _task_or_404(task_id, tasks)
        if error:
            return error
        if "title" in data:
            task["title"] = data["title"].strip()
        if "status" in data:
            task["status"] = data["status"]
        _write_tasks(tasks)
    return jsonify(task)


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
