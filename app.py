"""
Task Management Flask API

Provides CRUD endpoints for tasks backed by SQLite.

The tasks table intentionally does NOT use AUTOINCREMENT on its primary
key, so the id is assigned manually on every POST by computing
max(existing id) + 1 and inserting it explicitly.
"""

from datetime import datetime
import os
import sqlite3

from flask import Flask, jsonify, request

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _next_id(conn):
    row = conn.execute("SELECT MAX(id) AS max_id FROM tasks").fetchone()
    max_id = row["max_id"] if row and row["max_id"] is not None else 0
    return max_id + 1


def _serialize(row):
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
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status") or "pending"
    created_at = datetime.utcnow().isoformat()
    with get_db() as conn:
        task_id = _next_id(conn)
        conn.execute(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
            (task_id, title, status, created_at),
        )
        conn.commit()
    return (
        jsonify(
            {
                "id": task_id,
                "title": title,
                "status": status,
                "created_at": created_at,
            }
        ),
        201,
    )


@app.route("/tasks", methods=["GET"])
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return jsonify([_serialize(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(_serialize(row))


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
        if not title or not str(title).strip():
            return jsonify({"error": "title is required"}), 400
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (str(title).strip(), str(status).strip(), task_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(_serialize(updated))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
