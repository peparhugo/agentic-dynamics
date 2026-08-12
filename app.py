"""
Task API — Flask + SQLite.

Endpoints:
    POST /tasks          create a task
    GET  /tasks          list tasks ordered by created_at desc
    GET  /tasks/{id}     get a single task
    PUT  /tasks/{id}     update task title and/or status
"""

from flask import Flask
from flask import request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT NOT NULL
);
"""


# ── Database ────────────────────────────────────────────────────

def get_database_path():
    return app.config.get("DATABASE") or os.environ.get("DATABASE", "tasks.db")


def get_db():
    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)


# ── Helpers ─────────────────────────────────────────────────────

def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def fetch_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return row


# ── Routes ──────────────────────────────────────────────────────

@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or str(title).strip() == "":
        return jsonify({"error": "title is required"}), 400
    status = data.get("status") or "pending"
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (str(title).strip(), status, now),
        )
        conn.commit()
        task_id = cursor.lastrowid
    return jsonify({
        "id": task_id,
        "title": str(title).strip(),
        "status": status,
        "created_at": now,
    }), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([serialize_task(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    row = fetch_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(serialize_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    row = fetch_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is not None:
        title = str(title).strip()
        if title == "":
            return jsonify({"error": "title cannot be empty"}), 400
    else:
        title = row["title"]
    status = data.get("status", row["status"])
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        conn.commit()
    return jsonify(serialize_task(fetch_task(task_id)))


# ── Error handlers ──────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "method not allowed"}), 405


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
