"""
Task Management Flask API

A simple REST API for managing tasks with SQLite persistence.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()


def dict_from_row(row):
    """Convert sqlite3.Row to dict."""
    return dict(row) if row else None


@app.route("/tasks", methods=["POST"])
def create_task():
    """Create a new task."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, "pending", now)
        )
        conn.commit()
        task_id = cursor.lastrowid

    return jsonify({
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": now
    }), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    """List all tasks ordered by created_at descending."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, created_at FROM tasks ORDER BY created_at DESC"
        ).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    """Get a single task by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

    if row is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    """Update task title and/or status."""
    data = request.get_json(silent=True) or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        if row is None:
            return jsonify({"error": "task not found"}), 404

        task = dict(row)

        # Update title only if provided and not empty
        if "title" in data:
            stripped_title = data.get("title", "").strip()
            if stripped_title:
                title = stripped_title
            else:
                title = task["title"]
        else:
            title = task["title"]

        status = data.get("status", task["status"])

        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id)
        )
        conn.commit()

        task["title"] = title
        task["status"] = status

    return jsonify(task)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
