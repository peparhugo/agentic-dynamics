"""Flask API for managing tasks stored in SQLite."""

from datetime import datetime, timezone
import os
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db() -> sqlite3.Connection:
    """Return a connection configured to expose rows by column name."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the task storage schema if it does not already exist."""
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


def task_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_task(task_id: int) -> sqlite3.Row | None:
    with get_db() as connection:
        return connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
            (title.strip(), created_at),
        )
        task_id = cursor.lastrowid

    return jsonify(task_dict(get_task(task_id))), 201


@app.get("/tasks")
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return jsonify([task_dict(row) for row in rows])


@app.get("/tasks/<int:task_id>")
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_dict(task))


@app.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not any(key in data for key in ("title", "status")):
        return jsonify({"error": "title or status is required"}), 400

    title = task["title"]
    status = task["status"]
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title is required"}), 400
        title = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status is required"}), 400
        status = data["status"].strip()

    with get_db() as connection:
        connection.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
    return jsonify(task_dict(get_task(task_id)))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
