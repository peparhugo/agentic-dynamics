import sqlite3
import os
from datetime import datetime, timezone

from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")


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
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


init_db()


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True)
    if not data or "title" not in data or not data["title"]:
        return jsonify({"error": "Missing title"}), 400

    title = data["title"]
    status = data.get("status", "pending")
    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
        (title, status, created_at),
    )
    conn.commit()
    task_id = cursor.lastrowid
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()

    return jsonify(dict(task)), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([dict(task) for task in tasks])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(dict(task))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    title = data.get("title", task["title"])
    status = data.get("status", task["status"])

    conn.execute(
        "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
        (title, status, task_id),
    )
    conn.commit()
    updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()

    return jsonify(dict(updated))
