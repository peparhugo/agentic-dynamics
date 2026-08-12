"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", ":memory:")
_connection = sqlite3.connect(DATABASE, check_same_thread=False)
_connection.row_factory = sqlite3.Row


def get_db():
    return _connection


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.commit()


# ── Models ────────────────────────────────────────────────────

def create_task(title: str) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)",
            (title, now),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
        }


def get_tasks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    task = get_task(task_id)
    if task is None:
        return None
    with get_db() as conn:
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
    return get_task(task_id)


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str):
        title = ""
    title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
