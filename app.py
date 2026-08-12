from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")


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


def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def get_task_or_404(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return row


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status", "pending")
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title, status, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(serialize_task(row)), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC"
        ).fetchall()
    return jsonify([serialize_task(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    row = get_task_or_404(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(serialize_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    row = get_task_or_404(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(serialize_task(updated))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
