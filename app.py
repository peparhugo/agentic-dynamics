"""A small Flask API for managing tasks."""

from datetime import datetime, timezone
import os
import sqlite3

from flask import Flask, jsonify, request


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")


def get_db():
    """Open the configured SQLite database with dictionary-like rows."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def create_tasks_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )


def task_from_row(row):
    return dict(row)


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        # The schema is created lazily when the first task is inserted.
        create_tasks_table(connection)
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at) VALUES (?, ?)",
            (title, created_at),
        )
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        connection.commit()
    return jsonify(task_from_row(row)), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    try:
        with get_db() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC, id DESC"
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    return jsonify([task_from_row(row) for row in rows])


def find_task(task_id):
    with get_db() as connection:
        return connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    try:
        row = find_task(task_id)
    except sqlite3.OperationalError:
        row = None
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_from_row(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    fields = []
    values = []
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        fields.append("title = ?")
        values.append(data["title"].strip())
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status must be a non-empty string"}), 400
        fields.append("status = ?")
        values.append(data["status"].strip())
    if not fields:
        return jsonify({"error": "title or status is required"}), 400

    values.append(task_id)
    try:
        with get_db() as connection:
            cursor = connection.execute(
                f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?", values
            )
            if cursor.rowcount == 0:
                return jsonify({"error": "task not found"}), 404
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            connection.commit()
    except sqlite3.OperationalError:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_from_row(row))


if __name__ == "__main__":
    app.run(debug=True)
