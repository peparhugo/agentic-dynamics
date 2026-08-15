import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, current_app, jsonify, request


_storage_lock = threading.RLock()


def _storage_path() -> Path:
    return Path(current_app.config["TASKS_FILE"])


def init_storage(path: str | os.PathLike[str] | None = None) -> None:
    """Create the task data file if it does not already exist."""
    storage = Path(path) if path is not None else _storage_path()
    storage.parent.mkdir(parents=True, exist_ok=True)
    with _storage_lock:
        if not storage.exists():
            storage.write_text("[]\n", encoding="utf-8")


def _read_tasks() -> list[dict]:
    storage = _storage_path()
    if not storage.exists():
        init_storage(storage)
    try:
        data = json.loads(storage.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Task storage could not be read") from exc
    if not isinstance(data, list):
        raise RuntimeError("Task storage has an invalid format")
    return data


def _write_tasks(tasks: list[dict]) -> None:
    storage = _storage_path()
    storage.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=storage.parent, prefix=f".{storage.name}.", text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temporary_file:
            json.dump(tasks, temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, storage)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        TASKS_FILE=os.environ.get(
            "TASKS_FILE", str(Path(app.instance_path) / "tasks.json")
        )
    )
    if config:
        app.config.update(config)

    init_storage(app.config["TASKS_FILE"])

    @app.post("/tasks")
    def create_task():
        data = _json_body()
        title = data.get("title") if data is not None else None
        if not isinstance(title, str) or not title.strip():
            return jsonify(error="title is required"), 400

        with _storage_lock:
            tasks = _read_tasks()
            task = {
                "id": max((task["id"] for task in tasks), default=0) + 1,
                "title": title.strip(),
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            tasks.append(task)
            _write_tasks(tasks)
        return jsonify(task), 201

    @app.get("/tasks")
    def list_tasks():
        with _storage_lock:
            tasks = _read_tasks()
        tasks.sort(key=lambda task: task["created_at"], reverse=True)
        return jsonify(tasks)

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id: int):
        with _storage_lock:
            tasks = _read_tasks()
        task = next((task for task in tasks if task["id"] == task_id), None)
        if task is None:
            return jsonify(error="task not found"), 404
        return jsonify(task)

    @app.put("/tasks/<int:task_id>")
    def update_task(task_id: int):
        data = _json_body()
        if data is None:
            return jsonify(error="JSON object is required"), 400

        if "title" in data and (
            not isinstance(data["title"], str) or not data["title"].strip()
        ):
            return jsonify(error="title must be a non-empty string"), 400
        if "status" in data and (
            not isinstance(data["status"], str) or not data["status"].strip()
        ):
            return jsonify(error="status must be a non-empty string"), 400
        if not any(field in data for field in ("title", "status")):
            return jsonify(error="title or status is required"), 400

        with _storage_lock:
            tasks = _read_tasks()
            task = next((task for task in tasks if task["id"] == task_id), None)
            if task is None:
                return jsonify(error="task not found"), 404
            if "title" in data:
                task["title"] = data["title"].strip()
            if "status" in data:
                task["status"] = data["status"].strip()
            _write_tasks(tasks)
        return jsonify(task)

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
