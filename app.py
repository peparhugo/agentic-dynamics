"""A small Flask API for managing tasks.

Tasks are persisted in a JSON file.  The explicit flat-file storage
requirement means this service does not use a database.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from threading import Lock

from flask import Flask, jsonify, request


app = Flask(__name__)
DATA_FILE = Path(os.environ.get("TASKS_FILE", "tasks.json"))
_file_lock = Lock()


def init_storage():
    """Create the flat-file storage and its initial document if needed."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        _write_data({"next_id": 1, "tasks": []})


def _read_data():
    init_storage()
    try:
        with DATA_FILE.open("r", encoding="utf-8") as data_file:
            data = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        data = {"next_id": 1, "tasks": []}
    data.setdefault("next_id", 1)
    data.setdefault("tasks", [])
    return data


def _write_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=DATA_FILE.parent, prefix=f".{DATA_FILE.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(data, temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, DATA_FILE)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _task_response(task):
    return jsonify(task)


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not data["title"].strip():
        return jsonify({"error": "title is required"}), 400

    with _file_lock:
        storage = _read_data()
        task = {
            "id": storage["next_id"],
            "title": data["title"].strip(),
            "status": "pending",
            "created_at": _now(),
        }
        storage["next_id"] += 1
        storage["tasks"].append(task)
        _write_data(storage)
    return _task_response(task), 201


@app.get("/tasks")
def list_tasks():
    with _file_lock:
        tasks = list(_read_data()["tasks"])
    tasks.sort(key=lambda task: (task.get("created_at", ""), task.get("id", 0)), reverse=True)
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
def get_task(task_id):
    with _file_lock:
        task = next((task for task in _read_data()["tasks"] if task["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return _task_response(task)


@app.put("/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    if not ("title" in data or "status" in data):
        return jsonify({"error": "title or status is required"}), 400

    with _file_lock:
        storage = _read_data()
        task = next((task for task in storage["tasks"] if task["id"] == task_id), None)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        if "title" in data:
            task["title"] = data["title"].strip()
        if "status" in data:
            task["status"] = data["status"]
        _write_data(storage)
    return _task_response(task)


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "method not allowed"}), 405


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
