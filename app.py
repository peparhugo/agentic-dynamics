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
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def error(message, status_code):
    return jsonify({"error": message}), status_code


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("title is required", 400)

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return error("title is required", 400)

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    connection = get_db()
    try:
        # Reserve the database for writing while deriving the next ID.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM tasks"
        ).fetchone()
        task_id = row["next_id"]
        connection.execute(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
            (task_id, title, "pending", created_at),
        )
        connection.commit()
    finally:
        connection.close()

    return jsonify(
        {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }
    ), 201


@app.get("/tasks")
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return jsonify([task_json(row) for row in rows])


@app.get("/tasks/<int:task_id>")
def get_task(task_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    if row is None:
        return error("task not found", 404)
    return jsonify(task_json(row))


@app.put("/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("JSON object is required", 400)

    updates = []
    values = []

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            return error("title must be a non-empty string", 400)
        updates.append("title = ?")
        values.append(title.strip())

    if "status" in data:
        status = data["status"]
        if not isinstance(status, str) or not status.strip():
            return error("status must be a non-empty string", 400)
        updates.append("status = ?")
        values.append(status.strip())

    if not updates:
        return error("title or status is required", 400)

    with get_db() as connection:
        existing = connection.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if existing is None:
            return error("task not found", 404)

        values.append(task_id)
        connection.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values
        )
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    return jsonify(task_json(row))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
