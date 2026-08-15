"""Task management Flask API with SQLite persistence."""

from datetime import datetime, timezone
import os
import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")

VALID_STATUSES = {"pending", "done"}


def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def task_to_dict(row):
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
    if not title or not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    title = title.strip()
    status = data.get("status", "pending")
    if status not in VALID_STATUSES:
        return jsonify({"error": "invalid status"}), 422
    now = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, status, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return jsonify(task_to_dict(row)), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([task_to_dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        title = data.get("title", row["title"])
        status = data.get("status", row["status"])
        if status not in VALID_STATUSES:
            return jsonify({"error": "invalid status"}), 422
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(task_to_dict(row))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
