"""Flask API for managing tasks in memory."""

from datetime import datetime, timezone
from threading import Lock

from flask import Flask, jsonify, request


app = Flask(__name__)

_store: dict[str, object] = {}
_store_lock = Lock()


def init_db() -> None:
    """Initialize the in-memory equivalent of the task schema."""
    global _store
    with _store_lock:
        _store = {"tasks": [], "next_id": 1}


def create_task(title: str) -> dict:
    with _store_lock:
        task = {
            "id": _store["next_id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _store["next_id"] += 1
        _store["tasks"].append(task)
        return task.copy()


def get_tasks() -> list[dict]:
    with _store_lock:
        tasks = sorted(
            _store["tasks"],
            key=lambda task: (task["created_at"], task["id"]),
            reverse=True,
        )
        return [task.copy() for task in tasks]


def get_task(task_id: int) -> dict | None:
    with _store_lock:
        for task in _store["tasks"]:
            if task["id"] == task_id:
                return task.copy()
    return None


def fetch_task(task_id: int) -> dict | None:
    return get_task(task_id)


def update_task(
    task_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    with _store_lock:
        for task in _store["tasks"]:
            if task["id"] != task_id:
                continue
            if title is not None:
                task["title"] = title
            if status is not None:
                task["status"] = status
            return task.copy()
    return None


@app.get("/tasks")
def list_tasks():
    return jsonify(get_tasks())


@app.post("/tasks")
def add_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title.strip())), 201


@app.get("/tasks/<int:task_id>")
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
def edit_task(task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    task = update_task(task_id, title=data.get("title"), status=data.get("status"))
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
