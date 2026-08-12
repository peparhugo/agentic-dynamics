"""
Task management Flask API.

Storage: a single flat JSON file (no database). The schema is
initialized on startup by creating the file if it does not exist.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
import threading

app = Flask(__name__)

DATA_FILE = os.environ.get("DATA_FILE", "tasks.json")
_lock = threading.RLock()


def _empty_store():
    return {"tasks": [], "next_id": 1}


def _read_store() -> dict:
    with _lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            data = _empty_store()
            _write_store(data)
        except (json.JSONDecodeError, ValueError):
            data = _empty_store()
        return data


def _write_store(data: dict) -> None:
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, DATA_FILE)


def init_store():
    """Initialize the flat-file schema on startup."""
    _read_store()


# ── Models ────────────────────────────────────────────────────


def create_task(title: str) -> dict:
    with _lock:
        data = _read_store()
        task = {
            "id": data["next_id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        data["tasks"].append(task)
        data["next_id"] += 1
        _write_store(data)
        return task


def get_tasks():
    data = _read_store()
    return sorted(data["tasks"], key=lambda t: t["created_at"], reverse=True)


def get_task(task_id: int) -> dict | None:
    data = _read_store()
    for task in data["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    with _lock:
        data = _read_store()
        for task in data["tasks"]:
            if task["id"] == task_id:
                if title is not None:
                    task["title"] = title
                if status is not None:
                    task["status"] = status
                _write_store(data)
                return task
        return None


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
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
    status = data.get("status")
    if title is not None and not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    task = update_task(task_id, title=title, status=status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_store()
    app.run(debug=True)
