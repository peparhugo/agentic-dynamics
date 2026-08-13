"""
Flask Task Management API

Endpoints:
- POST /tasks — create a task
- GET /tasks — list all tasks
- GET /tasks/{id} — get a single task
- PUT /tasks/{id} — update a task
"""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)


def get_db():
    db_path = os.environ.get("DATABASE", "tasks.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    db_path = os.environ.get("DATABASE", "tasks.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)


def task_to_dict(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")

    if title is None:
        return jsonify({"error": "title is required"}), 400

    title = str(title).strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, "pending", now),
        )
        conn.commit()
        task_id = cursor.lastrowid

    return jsonify({
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": now,
    }), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([task_to_dict(row) for row in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    if row is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "task not found"}), 404

        title = data.get("title")
        status = data.get("status")

        if title is not None:
            title = str(title).strip()
        if status is not None:
            status = str(status).strip()

        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return jsonify(task_to_dict(row))

        params.append(task_id)
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        conn.execute(query, params)
        conn.commit()

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    return jsonify(task_to_dict(row))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
