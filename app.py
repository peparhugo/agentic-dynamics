"""Minimal Flask Task Management API backed by SQLite."""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )


# ── Models ────────────────────────────────────────────────────


def create_task(title: str) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        next_id = conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM tasks"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, 'pending', ?)",
            (next_id, title, now),
        )
        conn.commit()
        return {
            "id": next_id,
            "title": title,
            "status": "pending",
            "created_at": now,
        }


def get_tasks() -> list[dict]:
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
    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = create_task(title.strip())
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


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
