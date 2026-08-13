"""
Flask API for task management.

Storage is flat-file JSON (see storage.py) — no database is used, per the
project's storage constraint.
"""

import os

from flask import Flask, jsonify, request

from storage import TaskStore

DEFAULT_STORAGE_PATH = os.environ.get("TASKS_STORAGE_PATH", "tasks.json")


def create_app(storage_path: str = DEFAULT_STORAGE_PATH) -> Flask:
    app = Flask(__name__)
    app.store = TaskStore(storage_path)

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not found"}), 404

    @app.post("/tasks")
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = app.store.create(title.strip())
        return jsonify(task), 201

    @app.get("/tasks")
    def list_tasks():
        return jsonify(app.store.list_all()), 200

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id):
        task = app.store.get(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task), 200

    @app.put("/tasks/<int:task_id>")
    def update_task(task_id):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        status = data.get("status")

        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400
        if title is not None and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400
        if status is not None and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400

        task = app.store.update(
            task_id,
            title=title.strip() if title is not None else None,
            status=status.strip() if status is not None else None,
        )
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
