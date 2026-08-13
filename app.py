import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, request


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
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


def create_task(title):
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
            (title, created_at),
        )
        task_id = cursor.lastrowid
    return get_task(task_id)


def get_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return dict(row) if row else None


def update_task(task_id, title=None, status=None):
    if get_task(task_id) is None:
        return None

    updates = []
    values = []
    if title is not None:
        updates.append("title = ?")
        values.append(title)
    if status is not None:
        updates.append("status = ?")
        values.append(status)

    if updates:
        values.append(task_id)
        with get_db() as connection:
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values
            )
    return get_task(task_id)


@app.get("/tasks")
def list_tasks():
    return jsonify(get_tasks())


@app.post("/tasks")
def add_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400
    return jsonify(create_task(title.strip())), 201


@app.get("/tasks/<int:task_id>")
def show_task(task_id):
    task = get_task(task_id)
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
def edit_task(task_id):
    if get_task(task_id) is None:
        return jsonify(error="task not found"), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON object is required"), 400

    title = data.get("title")
    status = data.get("status")
    if "title" in data and (not isinstance(title, str) or not title.strip()):
        return jsonify(error="title must be a non-empty string"), 400
    if "status" in data and not isinstance(status, str):
        return jsonify(error="status must be a string"), 400

    task = update_task(
        task_id,
        title=title.strip() if isinstance(title, str) else None,
        status=status,
    )
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
