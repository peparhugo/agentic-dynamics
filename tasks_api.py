"""Flask API for task management, backed by SQLite.

SQLite's INTEGER PRIMARY KEY without AUTOINCREMENT can still reuse ids after
deletes, so task ids are assigned manually from a counter persisted in a
dedicated `counters` table rather than relying on SQLite's rowid behavior.
"""

import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counters (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
        conn.execute("INSERT OR IGNORE INTO counters (name, value) VALUES ('task_id', 1)")
        conn.commit()
    finally:
        conn.close()


def _next_task_id(db):
    """Reserve and return the next task id, persisting the incremented counter."""
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT value FROM counters WHERE name = 'task_id'").fetchone()
    next_id = row["value"]
    db.execute("UPDATE counters SET value = ? WHERE name = 'task_id'", (next_id + 1,))
    return next_id


def _task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or DEFAULT_DB_PATH
    init_db(app.config["DB_PATH"])

    def get_db():
        db = getattr(g, "_database", None)
        if db is None:
            db = g._database = sqlite3.connect(app.config["DB_PATH"])
            db.row_factory = sqlite3.Row
        return db

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("_database", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.post("/tasks")
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        db = get_db()
        task_id = _next_task_id(db)
        created_at = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO tasks (id, title, status, created_at) VALUES (?, ?, ?, ?)",
            (task_id, title, "pending", created_at),
        )
        db.commit()

        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify(_task_to_dict(row)), 201

    @app.get("/tasks")
    def list_tasks():
        db = get_db()
        rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC, id DESC").fetchall()
        return jsonify([_task_to_dict(r) for r in rows]), 200

    @app.get("/tasks/<int:task_id>")
    def get_task(task_id):
        db = get_db()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404
        return jsonify(_task_to_dict(row)), 200

    @app.put("/tasks/<int:task_id>")
    def update_task(task_id):
        db = get_db()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404

        data = request.get_json(silent=True) or {}
        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400

        title = row["title"]
        status = row["status"]

        if "title" in data:
            new_title = data["title"]
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            title = new_title

        if "status" in data:
            new_status = data["status"]
            if not isinstance(new_status, str) or not new_status.strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            status = new_status

        db.execute("UPDATE tasks SET title = ?, status = ? WHERE id = ?", (title, status, task_id))
        db.commit()

        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify(_task_to_dict(row)), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
