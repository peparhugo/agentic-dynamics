"""Flask task management API with SQLite persistence."""

import os
import time
import sqlite3

from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


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
    if title is None or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    now = int(time.time())
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)",
        (title, now),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return jsonify(
        {"id": task_id, "title": title, "status": "pending", "created_at": now}
    ), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([task_to_dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "task not found"}), 404

    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    if title is not None:
        title = str(title).strip()
        if not title:
            conn.close()
            return jsonify({"error": "title is required"}), 400
    if not status:
        conn.close()
        return jsonify({"error": "status is required"}), 400

    conn.execute(
        "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
        (title, status, task_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return jsonify(task_to_dict(updated))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
