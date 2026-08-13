"""
Flask Task Management API

A simple task management API with SQLite persistence.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")


# ── Database ────────────────────────────────────────────────────

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


# ── Helper Functions ────────────────────────────────────────────

def task_to_dict(row):
    """Convert a database row to a dictionary."""
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


# ── Task Endpoints ──────────────────────────────────────────────

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
    """List all tasks ordered by created_at descending."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()

    return jsonify([task_to_dict(row) for row in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    """Get a single task by ID."""
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
    """Update a task's title and/or status."""
    data = request.get_json(silent=True) or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if row is None:
            return jsonify({"error": "task not found"}), 404

        title = data.get("title", row["title"]).strip() if "title" in data else row["title"]
        status = data.get("status", row["status"]) if "status" in data else row["status"]

        if "title" in data and not title:
            return jsonify({"error": "title cannot be empty"}), 400

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


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
