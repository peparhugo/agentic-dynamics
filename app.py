import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


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


def task_response(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


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
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, "pending", created_at),
        )
        task_id = cursor.lastrowid

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
    return jsonify([task_response(row) for row in rows])


@app.get("/tasks/<int:task_id>")
def get_task(task_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_response(row))


@app.put("/tasks/<int:task_id>")
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body is required"}), 400

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

    with get_db() as connection:
        exists = connection.execute(
            "SELECT id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if exists is None:
            return jsonify({"error": "task not found"}), 404
        if updates:
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                (*values, task_id),
            )
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    return jsonify(task_response(row))


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({"error": error.description}), error.code


init_db()


if __name__ == "__main__":
    app.run(debug=True)
