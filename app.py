"""
Flask Task Management API.

Storage: flat JSON file (no database), per the "no databases allowed" constraint.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timezone
import json
import os
import threading

app = Flask(__name__)

DATA_FILE = os.environ.get("DATA_FILE", "tasks.json")

_lock = threading.Lock()


# ── Storage ───────────────────────────────────────────────────

def init_db():
    """Initialize the flat-file store on startup if it doesn't exist."""
    if not os.path.exists(DATA_FILE):
        _write_tasks([])


def _read_tasks() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        content = f.read().strip()
        return json.loads(content) if content else []


def _write_tasks(tasks: list) -> None:
    tmp_path = f"{DATA_FILE}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(tasks, f, indent=2)
    os.replace(tmp_path, DATA_FILE)


def _next_id(tasks: list) -> int:
    return max((t["id"] for t in tasks), default=0) + 1


# ── Models ────────────────────────────────────────────────────

def create_task(title: str) -> dict:
    with _lock:
        tasks = _read_tasks()
        task = {
            "id": _next_id(tasks),
            "title": title,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tasks.append(task)
        _write_tasks(tasks)
        return task


def get_tasks() -> list:
    tasks = _read_tasks()
    return sorted(tasks, key=lambda t: t["created_at"], reverse=True)


def get_task(task_id: int) -> dict | None:
    tasks = _read_tasks()
    return next((t for t in tasks if t["id"] == task_id), None)


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    with _lock:
        tasks = _read_tasks()
        task = next((t for t in tasks if t["id"] == task_id), None)
        if task is None:
            return None
        if title is not None:
            task["title"] = title
        if status is not None:
            task["status"] = status
        _write_tasks(tasks)
        return task


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not isinstance(title, str) or not title.strip():
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
    data = request.get_json(silent=True) or {}

    title = data.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400

    status = data.get("status")
    if status is not None and (not isinstance(status, str) or not status.strip()):
        return jsonify({"error": "status must be a non-empty string"}), 400

    task = update_task(
        task_id,
        title=title.strip() if title is not None else None,
        status=status.strip() if status is not None else None,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
