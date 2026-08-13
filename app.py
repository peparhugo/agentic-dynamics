import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, request


DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
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


def task_to_dict(task: sqlite3.Row) -> dict:
    return {
        "id": task["id"],
        "title": task["title"],
        "status": task["status"],
        "created_at": task["created_at"],
    }


def json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def create_app(config: dict | None = None) -> Flask:
    global DATABASE

    application = Flask(__name__)
    if config:
        application.config.update(config)
        if config.get("DATABASE"):
            DATABASE = config["DATABASE"]

    @application.post("/tasks")
    def create_task():
        data = json_body()
        title = data.get("title") if data else None
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        title = title.strip()
        created_at = datetime.now(timezone.utc).isoformat()
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
                (title, created_at),
            )
            task = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()

        return jsonify(task_to_dict(task)), 201

    @application.get("/tasks")
    def list_tasks():
        with get_db() as connection:
            tasks = connection.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return jsonify([task_to_dict(task) for task in tasks])

    @application.get("/tasks/<int:task_id>")
    def get_task(task_id: int):
        with get_db() as connection:
            task = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task_to_dict(task))

    @application.put("/tasks/<int:task_id>")
    def update_task(task_id: int):
        data = json_body()
        if data is None:
            return jsonify({"error": "JSON object is required"}), 400

        updates = []
        values = []
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            updates.append("title = ?")
            values.append(data["title"].strip())
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            updates.append("status = ?")
            values.append(data["status"].strip())
        if not updates:
            return jsonify({"error": "title or status is required"}), 400

        with get_db() as connection:
            existing = connection.execute(
                "SELECT id FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if existing is None:
                return jsonify({"error": "task not found"}), 404

            values.append(task_id)
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values
            )
            task = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()

        return jsonify(task_to_dict(task))

    init_db()
    return application


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
