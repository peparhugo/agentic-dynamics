"""
Flask API for task management, backed by SQLite.

Models:
    Task: id (int, auto), title (str), status (str, default 'pending'), created_at (datetime)

Endpoints:
    POST   /tasks       create a task
    GET    /tasks       list all tasks ordered by created_at desc
    GET    /tasks/<id>  get a single task
    PUT    /tasks/<id>  update task title and/or status
"""

import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request

DATABASE = os.environ.get("DATABASE", "tasks.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
"""

VALID_STATUSES = {"pending", "in_progress", "completed"}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.get("db_path", DATABASE))
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db(database_path):
    conn = sqlite3.connect(database_path)
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def create_app(database_path=None):
    app = Flask(__name__)
    db_path = database_path or DATABASE
    app.config["DATABASE"] = db_path
    init_db(db_path)

    @app.before_request
    def _set_db_path():
        g.db_path = app.config["DATABASE"]

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="Bad request"), 400

    @app.route("/tasks", methods=["POST"])
    def create_task():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Request body must be a JSON object"), 400
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify(error="title is required"), 400

        status = data.get("status", "pending")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            return jsonify(error=f"status must be one of {sorted(VALID_STATUSES)}"), 400

        created_at = datetime.now(timezone.utc).isoformat()
        db = get_db()
        cur = db.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title.strip(), status, created_at),
        )
        db.commit()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(task_to_dict(row)), 201

    @app.route("/tasks", methods=["GET"])
    def list_tasks():
        db = get_db()
        rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC, id DESC").fetchall()
        return jsonify([task_to_dict(row) for row in rows]), 200

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id):
        db = get_db()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return jsonify(error="Task not found"), 404
        return jsonify(task_to_dict(row)), 200

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        db = get_db()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return jsonify(error="Task not found"), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Request body must be a JSON object"), 400

        title = row["title"]
        status = row["status"]

        if "title" in data:
            new_title = data["title"]
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify(error="title must be a non-empty string"), 400
            title = new_title.strip()

        if "status" in data:
            new_status = data["status"]
            if not isinstance(new_status, str) or new_status not in VALID_STATUSES:
                return jsonify(error=f"status must be one of {sorted(VALID_STATUSES)}"), 400
            status = new_status

        db.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        db.commit()
        updated = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify(task_to_dict(updated)), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
