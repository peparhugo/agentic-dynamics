"""Flask task-management API backed by a JSON flat file."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from flask import Flask, jsonify, request


app = Flask(__name__)

# Kept configurable so deployments and tests can use an isolated data file.
DATABASE = os.environ.get("DATABASE", "tasks.json")


def _empty_store() -> dict:
    return {"next_id": 1, "tasks": []}


def init_db() -> None:
    """Create the flat-file schema when the task store does not yet exist."""
    path = Path(DATABASE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        _write_store(_empty_store())


def _read_store() -> dict:
    init_db()
    with Path(DATABASE).open(encoding="utf-8") as data_file:
        return json.load(data_file)


def _write_store(store: dict) -> None:
    path = Path(DATABASE)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as data_file:
        json.dump(store, data_file)
    temporary_path.replace(path)


def create_task(title: str) -> dict:
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
    return task


def get_tasks() -> list[dict]:
    tasks = _read_store()["tasks"]
    return sorted(tasks, key=lambda task: task["created_at"], reverse=True)


def get_task(task_id: int) -> dict | None:
    for task in _read_store()["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    store = _read_store()
    for task in store["tasks"]:
        if task["id"] == task_id:
            if title is not None:
                task["title"] = title
            if status is not None:
                task["status"] = status
            _write_store(store)
            return task
    return None


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/tasks", methods=["POST"])
def add_task():
    data = _json_body()
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    task = create_task(title.strip())
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task(task_id: int):
    data = _json_body()
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400

    title = data.get("title")
    status = data.get("status")
    if "title" in data and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400

    task = update_task(task_id, title.strip() if title is not None else None, status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
