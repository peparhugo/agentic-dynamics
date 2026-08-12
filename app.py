"""
Flask Task Management API.

A single-file Flask app with clean structure: models, routes, error handling.
Uses SQLite for storage, with schema initialized on startup.
"""

from flask import Flask, request, jsonify, g, current_app
from datetime import datetime
import sqlite3
import os


def get_db():
    """Return a request-scoped SQLite connection, creating it if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(database_path: str) -> None:
    """Create the tasks table if it doesn't already exist."""
    conn = sqlite3.connect(database_path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.commit()
    finally:
        conn.close()


# ── Models ────────────────────────────────────────────────────

def create_task(title: str) -> dict:
    db = get_db()
    now = datetime.utcnow().isoformat()
    cursor = db.execute(
        "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)",
        (title, now),
    )
    db.commit()
    return {
        "id": cursor.lastrowid,
        "title": title,
        "status": "pending",
        "created_at": now,
    }


def get_tasks() -> list:
    db = get_db()
    rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


def get_task(task_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def update_task(task_id: int, title=None, status=None):
    db = get_db()
    task = get_task(task_id)
    if task is None:
        return None

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
        db.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()
    return get_task(task_id)


# ── App factory ───────────────────────────────────────────────

def create_app(database: str = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or os.environ.get("DATABASE", "tasks.db")

    with app.app_context():
        init_db(app.config["DATABASE"])

    app.teardown_appcontext(close_db)

    # ── Routes ───────────────────────────────────────────────

    @app.route("/tasks", methods=["POST"])
    def add_task():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = create_task(title.strip())
        return jsonify(task), 201

    @app.route("/tasks", methods=["GET"])
    def list_tasks():
        return jsonify(get_tasks())

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def show_task(task_id: int):
        task = get_task(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task)

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    def edit_task(task_id: int):
        existing = get_task(task_id)
        if existing is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}

        title = data.get("title")
        status = data.get("status")

        if title is not None and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400
        if status is not None and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400
        if title is None and status is None:
            return jsonify({"error": "title and/or status is required"}), 400

        task = update_task(
            task_id,
            title=title.strip() if title is not None else None,
            status=status.strip() if status is not None else None,
        )
        return jsonify(task)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "method not allowed"}), 405

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
