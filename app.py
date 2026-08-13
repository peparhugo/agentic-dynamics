"""Flask task management API backed by a JSON flat file."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request


app = Flask(__name__)

# A JSON file keeps the application portable and satisfies the flat-file
# storage requirement. Tests or deployments may override this path.
DATA_FILE = os.environ.get("TASKS_FILE", "tasks.json")


def _data_path() -> Path:
    return Path(DATA_FILE)


def init_db() -> None:
    """Create the task store when it does not already exist."""
    path = _data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")


def _read_tasks() -> list[dict]:
    init_db()
    try:
        data = json.loads(_data_path().read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise RuntimeError("task storage contains invalid JSON")
    if not isinstance(data, list):
        raise RuntimeError("task storage must contain a JSON list")
    return data


def _write_tasks(tasks: list[dict]) -> None:
    path = _data_path()
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def create_task(title: str) -> dict:
    tasks = _read_tasks()
    task = {
        "id": max((task["id"] for task in tasks), default=0) + 1,
        "title": title,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    tasks.append(task)
    _write_tasks(tasks)
    return task


def get_tasks() -> list[dict]:
    return sorted(_read_tasks(), key=lambda task: task["created_at"], reverse=True)


def get_task(task_id: int) -> dict | None:
    return next((task for task in _read_tasks() if task["id"] == task_id), None)


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    tasks = _read_tasks()
    task = next((item for item in tasks if item["id"] == task_id), None)
    if task is None:
        return None
    if title is not None:
        task["title"] = title
    if status is not None:
        task["status"] = status
    _write_tasks(tasks)
    return task


def _title_from(data: dict) -> str | None:
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    return title.strip()


@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = _title_from(data)
    if title is None:
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title)), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if not any(field in data for field in ("title", "status")):
        return jsonify({"error": "title or status is required"}), 400
    title = None
    if "title" in data:
        title = _title_from(data)
        if title is None:
            return jsonify({"error": "title is required"}), 400
    status = data.get("status")
    if "status" in data and not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400
    task = update_task(task_id, title=title, status=status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
