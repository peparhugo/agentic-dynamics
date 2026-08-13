"""SQLite-backed task management API."""

import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, current_app, jsonify, request


def create_app(database: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or os.environ.get("DATABASE", "tasks.db")

    def get_db() -> sqlite3.Connection:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        return connection

    def init_db() -> None:
        with get_db() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
                """
            )

    def task_or_404(task_id: int) -> sqlite3.Row | None:
        with get_db() as connection:
            task = connection.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return task

    @app.post("/tasks")
    def create_task():
        data = request.get_json(silent=True)
        title = data.get("title") if isinstance(data, dict) else None
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        title = title.strip()
        created_at = datetime.now(timezone.utc).isoformat()
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
                (title, created_at),
            )
        return jsonify({
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }), 201

    @app.get("/tasks")
    def list_tasks():
        with get_db() as connection:
            tasks = connection.execute(
                "SELECT id, title, status, created_at FROM tasks ORDER BY created_at DESC"
            ).fetchall()
        return jsonify([dict(task) for task in tasks])

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id: int):
        task = task_or_404(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(dict(task))

    @app.put("/tasks/<int:task_id>")
    def update_task(task_id: int):
        task = task_or_404(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not {"title", "status"} & data.keys():
            return jsonify({"error": "title or status is required"}), 400

        updates = {}
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            updates["title"] = data["title"].strip()
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            updates["status"] = data["status"].strip()

        assignments = ", ".join(f"{column} = ?" for column in updates)
        with get_db() as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ?",
                (*updates.values(), task_id),
            )
        return jsonify({**dict(task), **updates})

    with app.app_context():
        init_db()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
