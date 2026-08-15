"""
Flask Todo API — flat-file storage.

A single-file Flask app with clean structure: models, routes, error handling.
All data is stored in a JSON flat file (no databases).
"""

from flask import Flask, request, jsonify
from datetime import datetime
import json
import os
import threading

app = Flask(__name__)

DATA_FILE = os.environ.get("DATA_FILE", "tasks.json")
_lock = threading.Lock()


def init_store() -> None:
    with _lock:
        if not os.path.exists(DATA_FILE):
            with open(DATA_FILE, "w") as f:
                json.dump({"tasks": [], "next_id": 1}, f)


def _read() -> dict:
    with open(DATA_FILE) as f:
        return json.load(f)


def _write(store: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(store, f, indent=2)


# ── Models ────────────────────────────────────────────────────

def create_task(title: str) -> dict:
    with _lock:
        store = _read()
        task = {
            "id": store["next_id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        store["tasks"].append(task)
        store["next_id"] += 1
        _write(store)
        return task


def get_tasks() -> list:
    store = _read()
    return sorted(store["tasks"], key=lambda t: t["created_at"], reverse=True)


def get_task(task_id: int) -> dict | None:
    store = _read()
    for task in store["tasks"]:
        if task["id"] == task_id:
            return task
    return None


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    with _lock:
        store = _read()
        for task in store["tasks"]:
            if task["id"] == task_id:
                if title is not None:
                    task["title"] = title
                if status is not None:
                    task["status"] = status
                _write(store)
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
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_store()
    app.run(debug=True)
