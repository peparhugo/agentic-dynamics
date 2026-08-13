"""
Flask Task Management API
SQLite-backed REST API for managing tasks.
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
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    with get_db() as conn:
        now = datetime.utcnow().isoformat()
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
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, created_at FROM tasks ORDER BY created_at DESC"
        ).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
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
    data = request.get_json(silent=True) or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        if row is None:
            return jsonify({"error": "task not found"}), 404

        title = data.get("title")
        status = data.get("status")

        if title is not None:
            title = title.strip()
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400

        if title is not None and status is not None:
            conn.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id)
            )
        elif title is not None:
            conn.execute(
                "UPDATE tasks SET title = ? WHERE id = ?",
                (title, task_id)
            )
        elif status is not None:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id)
            )

        conn.commit()

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

    return jsonify(dict(row))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
