import json
import os
import threading
from datetime import datetime

from flask import Flask, jsonify, request

app = Flask(__name__)
app.config["STORAGE_FILE"] = os.environ.get("TASKS_DB", "tasks.json")

_lock = threading.Lock()


def storage_file():
    return app.config["STORAGE_FILE"]


def init_storage():
    with _lock:
        path = storage_file()
        if not os.path.exists(path):
            _write_tasks([])


def _read_tasks():
    path = storage_file()
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def _write_tasks(tasks):
    with open(storage_file(), "w") as f:
        json.dump(tasks, f)


def _next_id(tasks):
    return max((t["id"] for t in tasks), default=0) + 1


def _find_task(tasks, task_id):
    return next((t for t in tasks if t["id"] == task_id), None)


@app.route("/tasks", methods=["POST"])
def create_task():
    init_storage()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    with _lock:
        tasks = _read_tasks()
        task = {
            "id": _next_id(tasks),
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        tasks.append(task)
        _write_tasks(tasks)
    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    init_storage()
    with _lock:
        tasks = _read_tasks()
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return jsonify(tasks)


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    init_storage()
    with _lock:
        task = _find_task(_read_tasks(), task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    init_storage()
    data = request.get_json(silent=True) or {}
    with _lock:
        tasks = _read_tasks()
        task = _find_task(tasks, task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                return jsonify({"error": "title is required"}), 400
            task["title"] = title
        if "status" in data:
            status = (data.get("status") or "").strip()
            if not status:
                return jsonify({"error": "status is required"}), 400
            task["status"] = status
        _write_tasks(tasks)
    return jsonify(task)


if __name__ == "__main__":
    init_storage()
    app.run(debug=True)
