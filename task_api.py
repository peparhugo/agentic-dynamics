"""
Task Management API

A Flask REST API backed by SQLite with a single Task model:
  - id (int, auto)
  - title (str)
  - status (str, default 'pending')
  - created_at (datetime)
"""

from datetime import datetime

from flask import Flask, jsonify, request
import sqlite3
import os

app = Flask(__name__)

DATABASE = os.environ.get("TASK_DATABASE", "tasks.db")

VALID_STATUSES = {"pending", "in_progress", "completed"}


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status", "pending")
    if status not in VALID_STATUSES:
        return jsonify({"error": "invalid status"}), 400
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, status, now),
        )
        conn.commit()
        task_id = cursor.lastrowid
    return jsonify({
        "id": task_id,
        "title": title,
        "status": status,
        "created_at": now,
    }), 201


@app.get("/tasks")
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(dict(row))


@app.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        data = request.get_json(silent=True) or {}
        title = data.get("title", row["title"])
        status = data.get("status", row["status"])
        if not title or not str(title).strip():
            return jsonify({"error": "title is required"}), 400
        title = str(title).strip()
        if status not in VALID_STATUSES:
            return jsonify({"error": "invalid status"}), 400
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        conn.commit()
    return jsonify({
        "id": task_id,
        "title": title,
        "status": status,
        "created_at": row["created_at"],
    })


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
