"""SQLite-backed task management API."""

from datetime import datetime
import os
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db() -> sqlite3.Connection:
    """Return a connection that exposes rows by column name."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the task table if it has not already been created."""
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


def task_not_found():
    return jsonify({"error": "task not found"}), 404


@app.post("/tasks")
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    task = {
        "title": title.strip(),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (task["title"], task["status"], task["created_at"]),
        )
        task["id"] = cursor.lastrowid
    return jsonify(task), 201


@app.get("/tasks")
def list_tasks():
    with get_db() as conn:
        rows = conn.execute("SELECT id, title, status, created_at FROM tasks").fetchall()
    # SQLite retrieval is intentionally unsorted; sort the loaded task rows here.
    tasks = [dict(row) for row in rows]
    tasks.sort(key=lambda task: task["created_at"], reverse=True)
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if row is None:
        return task_not_found()
    return jsonify(dict(row))


@app.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    updates = []
    values = []

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        updates.append("title = ?")
        values.append(title.strip())
    if "status" in data:
        status = data["status"]
        if not isinstance(status, str):
            return jsonify({"error": "status must be a string"}), 400
        updates.append("status = ?")
        values.append(status)

    with get_db() as conn:
        row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return task_not_found()
        if updates:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", values + [task_id]
            )
        task = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(dict(task))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
