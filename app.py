import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from flask import Flask, jsonify, request


app = Flask(__name__)
app.config["DATA_FILE"] = os.environ.get("TASKS_FILE", "tasks.json")

_storage_lock = RLock()


def _data_file() -> Path:
    return Path(app.config["DATA_FILE"])


def init_storage() -> None:
    """Create an empty task store if one does not already exist."""
    path = _data_file()
    with _storage_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            _write_tasks([])


def _read_tasks() -> list[dict]:
    init_storage()
    with _storage_lock:
        try:
            with _data_file().open(encoding="utf-8") as store:
                data = json.load(store)
        except (json.JSONDecodeError, OSError) as exc:
            raise RuntimeError("task storage is unreadable") from exc

    if not isinstance(data, list):
        raise RuntimeError("task storage is invalid")
    return data


def _write_tasks(tasks: list[dict]) -> None:
    path = _data_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as store:
            json.dump(tasks, store, indent=2)
            store.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def create_task(title: str) -> dict:
    with _storage_lock:
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
    tasks = _read_tasks()
    return sorted(tasks, key=lambda task: task["created_at"], reverse=True)


def get_task(task_id: int) -> dict | None:
    return next((task for task in _read_tasks() if task["id"] == task_id), None)


def update_task(
    task_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    with _storage_lock:
        tasks = _read_tasks()
        task = next((task for task in tasks if task["id"] == task_id), None)
        if task is None:
            return None
        if title is not None:
            task["title"] = title
        if status is not None:
            task["status"] = status
        _write_tasks(tasks)
        return task


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


@app.get("/tasks")
def list_tasks():
    return jsonify(get_tasks())


@app.post("/tasks")
def add_task():
    data = _json_body()
    title = data.get("title") if data is not None else None
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
    if get_task(task_id) is None:
        return jsonify({"error": "task not found"}), 404

    data = _json_body()
    if data is None:
        return jsonify({"error": "JSON object is required"}), 400
    if "title" in data and (
        not isinstance(data["title"], str) or not data["title"].strip()
    ):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    title = data["title"].strip() if "title" in data else None
    task = update_task(task_id, title=title, status=data.get("status"))
    return jsonify(task)


@app.errorhandler(404)
def route_not_found(_error):
    return jsonify({"error": "not found"}), 404


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
