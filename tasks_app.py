"""Flask API for task management, backed by SQLite."""

from flask import Flask, request, jsonify, g
from datetime import datetime
import sqlite3
import os

DATABASE = os.environ.get("TASKS_DATABASE", "tasks.db")


def create_app(database=None):
    app = Flask(__name__)
    app.config["DATABASE"] = database or DATABASE

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def init_db():
        conn = sqlite3.connect(app.config["DATABASE"])
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

    app.init_db = init_db
    init_db()

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad request"}), 400

    @app.route("/tasks", methods=["POST"])
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        now = datetime.utcnow().isoformat()
        db = get_db()
        cursor = db.execute(
            "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
            (title.strip(), "pending", now),
        )
        db.commit()
        row = db.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return jsonify(dict(row)), 201

    @app.route("/tasks", methods=["GET"])
    def list_tasks():
        db = get_db()
        rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return jsonify([dict(r) for r in rows])

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id):
        db = get_db()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(dict(row))

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        db = get_db()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True) or {}
        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400

        title = row["title"]
        status = row["status"]

        if "title" in data:
            new_title = data["title"]
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            title = new_title.strip()

        if "status" in data:
            new_status = data["status"]
            if not isinstance(new_status, str) or not new_status.strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            status = new_status.strip()

        db.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        db.commit()
        updated = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify(dict(updated))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
