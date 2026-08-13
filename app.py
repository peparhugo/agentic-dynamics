"""Flask API for managing tasks stored in SQLite."""

from datetime import datetime, timezone
import os
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "todos.db")


def get_db() -> sqlite3.Connection:
    """Create a SQLite connection configured to return mapping-like rows."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the task table when it does not already exist."""
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


def get_task(task_id: int) -> dict | None:
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return dict(row) if row else None


def validate_title(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True)
    title = validate_title(data.get("title")) if isinstance(data, dict) else None
    if title is None:
        return jsonify(error="title is required"), 400

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at) VALUES (?, ?)", (title, created_at)
        )
        task_id = cursor.lastrowid

    return jsonify(get_task(task_id)), 201


@app.get("/tasks")
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.get("/tasks/<int:task_id>")
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body is required"), 400

    updates = []
    parameters = []
    if "title" in data:
        title = validate_title(data["title"])
        if title is None:
            return jsonify(error="title must be a non-empty string"), 400
        updates.append("title = ?")
        parameters.append(title)
    if "status" in data:
        if not isinstance(data["status"], str):
            return jsonify(error="status must be a string"), 400
        updates.append("status = ?")
        parameters.append(data["status"])
    if not updates:
        return jsonify(error="title or status is required"), 400

    parameters.append(task_id)
    with get_db() as connection:
        cursor = connection.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", parameters
        )
        if cursor.rowcount == 0:
            return jsonify(error="task not found"), 404

    return jsonify(get_task(task_id))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
