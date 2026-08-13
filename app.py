"""
Flask Task Management API with flat-file storage.
Uses JSON files for persistence instead of databases.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
from pathlib import Path

app = Flask(__name__)

DATA_DIR = os.environ.get("DATA_DIR", "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")


# ── Storage initialization ──────────────────────────────────────

def get_data_dir():
    """Get the data directory, supporting dynamic monkeypatch in tests."""
    import app as app_module
    return app_module.DATA_DIR


def get_tasks_file():
    """Get the tasks file path, supporting dynamic monkeypatch in tests."""
    import app as app_module
    return app_module.TASKS_FILE


def ensure_data_dir():
    data_dir = get_data_dir()
    Path(data_dir).mkdir(exist_ok=True)


def init_tasks_file():
    ensure_data_dir()
    tasks_file = get_tasks_file()
    if not os.path.exists(tasks_file):
        with open(tasks_file, "w") as f:
            json.dump({"tasks": [], "next_id": 1}, f)


def load_tasks():
    init_tasks_file()
    tasks_file = get_tasks_file()
    with open(tasks_file, "r") as f:
        data = json.load(f)
    return data


def save_tasks(data):
    tasks_file = get_tasks_file()
    with open(tasks_file, "w") as f:
        json.dump(data, f, indent=2)


# ── Endpoints ───────────────────────────────────────────────────

@app.route("/tasks", methods=["POST"])
def create_task():
    """Create a new task. Requires 'title' in JSON body."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    tasks_data = load_tasks()
    task_id = tasks_data["next_id"]

    new_task = {
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }

    tasks_data["tasks"].append(new_task)
    tasks_data["next_id"] = task_id + 1
    save_tasks(tasks_data)

    return jsonify(new_task), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    """List all tasks ordered by created_at descending."""
    tasks_data = load_tasks()
    sorted_tasks = sorted(tasks_data["tasks"], key=lambda t: t["created_at"], reverse=True)
    return jsonify(sorted_tasks), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    """Get a single task by ID."""
    tasks_data = load_tasks()
    task = next((t for t in tasks_data["tasks"] if t["id"] == task_id), None)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    """Update a task's title and/or status."""
    data = request.get_json(silent=True) or {}
    tasks_data = load_tasks()

    task = next((t for t in tasks_data["tasks"] if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    if "title" in data:
        title = data["title"]
        if isinstance(title, str):
            title = title.strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        task["title"] = title

    if "status" in data:
        task["status"] = data["status"]

    save_tasks(tasks_data)
    return jsonify(task), 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    init_tasks_file()
    app.run(debug=True)
