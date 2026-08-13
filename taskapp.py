"""Flask API for task management, backed by SQLite."""

import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, request, jsonify


def get_db(database: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(database: str) -> None:
    conn = get_db(database)
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


def create_app(database: str = "tasks.db") -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database
    init_db(database)

    def db() -> sqlite3.Connection:
        return get_db(app.config["DATABASE"])

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "method not allowed"}), 405

    @app.route("/tasks", methods=["POST"])
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        now = datetime.now(timezone.utc).isoformat()
        conn = db()
        try:
            cur = conn.execute(
                "INSERT INTO tasks (title, status, created_at) VALUES (?, ?, ?)",
                (title.strip(), "pending", now),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        finally:
            conn.close()
        return jsonify(dict(row)), 201

    @app.route("/tasks", methods=["GET"])
    def list_tasks():
        conn = db()
        try:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC, id DESC"
            ).fetchall()
        finally:
            conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    def get_task(task_id):
        conn = db()
        try:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(dict(row))

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        conn = db()
        try:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                return jsonify({"error": "task not found"}), 404

            data = request.get_json(silent=True) or {}
            if not data:
                return jsonify({"error": "no fields to update"}), 400

            title = row["title"]
            status = row["status"]

            if "title" in data:
                new_title = data.get("title")
                if not isinstance(new_title, str) or not new_title.strip():
                    return jsonify({"error": "title must be a non-empty string"}), 400
                title = new_title.strip()

            if "status" in data:
                new_status = data.get("status")
                if not isinstance(new_status, str) or not new_status.strip():
                    return jsonify({"error": "status must be a non-empty string"}), 400
                status = new_status.strip()

            conn.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        finally:
            conn.close()
        return jsonify(dict(row))

    return app


if __name__ == "__main__":
    application = create_app(os.environ.get("DATABASE", "tasks.db"))
    application.run(debug=True)
