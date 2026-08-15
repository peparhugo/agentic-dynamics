import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from flask import Flask, jsonify, request


class TaskStore:
    """A small, thread-safe JSON file store for tasks."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.initialize()

    def initialize(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write([])

    def _read(self) -> list[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("task storage must contain a JSON array")
        return data

    def _write(self, tasks: list[dict[str, Any]]) -> None:
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(tasks, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, self.path)

    def create(self, title: str) -> dict[str, Any]:
        with self._lock:
            tasks = self._read()
            task = {
                "id": max((task["id"] for task in tasks), default=0) + 1,
                "title": title,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            tasks.append(task)
            self._write(tasks)
            return task

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(
                self._read(), key=lambda task: task["created_at"], reverse=True
            )

    def get(self, task_id: int) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (task for task in self._read() if task["id"] == task_id), None
            )

    def update(self, task_id: int, changes: dict[str, str]) -> dict[str, Any] | None:
        with self._lock:
            tasks = self._read()
            for task in tasks:
                if task["id"] == task_id:
                    task.update(changes)
                    self._write(tasks)
                    return task
            return None


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        TASKS_FILE=os.environ.get(
            "TASKS_FILE", str(Path(app.instance_path) / "tasks.json")
        )
    )
    if config:
        app.config.update(config)

    store = TaskStore(app.config["TASKS_FILE"])
    app.extensions["task_store"] = store

    @app.post("/tasks")
    def create_task():
        data = request.get_json(silent=True)
        title = data.get("title") if isinstance(data, dict) else None
        if not isinstance(title, str) or not title.strip():
            return jsonify(error="title is required"), 400

        return jsonify(store.create(title.strip())), 201

    @app.get("/tasks")
    def list_tasks():
        return jsonify(store.list())

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id: int):
        task = store.get(task_id)
        if task is None:
            return jsonify(error="task not found"), 404
        return jsonify(task)

    @app.put("/tasks/<int:task_id>")
    def update_task(task_id: int):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="JSON body is required"), 400

        changes = {}
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify(error="title must be a non-empty string"), 400
            changes["title"] = data["title"].strip()
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify(error="status must be a non-empty string"), 400
            changes["status"] = data["status"].strip()
        if not changes:
            return jsonify(error="title or status is required"), 400

        task = store.update(task_id, changes)
        if task is None:
            return jsonify(error="task not found"), 404
        return jsonify(task)

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
