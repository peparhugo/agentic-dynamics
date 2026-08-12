"""Flask API for managing tasks backed by SQLite."""

from datetime import datetime, timezone
import os
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    """Open the configured SQLite database with dictionary-like rows."""
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


def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def json_body():
    return request.get_json(silent=True) or {}


@app.route("/tasks", methods=["POST"])
def create_task():
    data = json_body()
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, "pending", created_at),
        )
        task_id = cursor.lastrowid
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return jsonify(serialize_task(row)), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return jsonify([serialize_task(row) for row in rows])


def find_task(task_id):
    with get_db() as connection:
        return connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    row = find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(serialize_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = json_body()
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400

    row = find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404

    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title must be a non-empty string"}), 400
    if not isinstance(status, str) or not status.strip():
        return jsonify({"error": "status must be a non-empty string"}), 400

    with get_db() as connection:
        connection.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title.strip(), status.strip(), task_id),
        )
        updated = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return jsonify(serialize_task(updated))


# Initialize the schema when the application module starts.
init_db()


if __name__ == "__main__":
    app.run(debug=True)
