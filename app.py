"""Flask API for managing tasks backed by SQLite."""

from datetime import datetime, timezone
import os
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    """Open a database connection configured to return named columns."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the task schema if it does not already exist."""
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


def task_dict(row):
    """Convert a SQLite row to the public task representation."""
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def json_body():
    """Return an object JSON body, or an empty object for absent JSON."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@app.post("/tasks")
def create_task():
    data = json_body()
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    status = data.get("status", "pending")
    if not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, status, created_at),
        )
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return jsonify(task_dict(row)), 201


@app.get("/tasks")
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return jsonify([task_dict(row) for row in rows])


def find_task(task_id):
    with get_db() as connection:
        return connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()


@app.get("/tasks/<int:task_id>")
def get_task(task_id):
    row = find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_dict(row))


@app.put("/tasks/<int:task_id>")
def update_task(task_id):
    data = json_body()
    supplied_fields = {field for field in ("title", "status") if field in data}
    if not supplied_fields:
        return jsonify({"error": "title or status is required"}), 400

    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        data["title"] = data["title"].strip()
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404

        title = data.get("title", row["title"])
        status = data.get("status", row["status"])
        connection.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        updated = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return jsonify(task_dict(updated))


init_db()


if __name__ == "__main__":
    app.run()
