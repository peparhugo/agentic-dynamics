import sqlite3
from datetime import datetime, timezone

from flask import Flask, current_app, g, jsonify, request

app = Flask(__name__)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db_path = current_app.config.get("DATABASE", "tasks.db")
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL
        )
        """
    )
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.route("/tasks", methods=["POST"])
def create_task():
    data = request.get_json(silent=True)
    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    title = data["title"]
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "Title is required"}), 400

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    cursor = db.execute(
        "INSERT INTO task (title, status, created_at) VALUES (?, 'pending', ?)",
        (title.strip(), now),
    )
    db.commit()

    task_id = cursor.lastrowid
    row = db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
    return jsonify(task_to_dict(row)), 201


@app.route("/tasks", methods=["GET"])
def list_tasks():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM task ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([task_to_dict(r) for r in rows]), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    db = get_db()
    row = db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task_to_dict(row)), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    db = get_db()
    row = db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(task_to_dict(row)), 200

    title = data.get("title", row["title"])
    status = data.get("status", row["status"])

    if isinstance(title, str) and not title.strip():
        return jsonify({"error": "Title is required"}), 400

    db.execute(
        "UPDATE task SET title = ?, status = ? WHERE id = ?",
        (title.strip() if isinstance(title, str) else title, status, task_id),
    )
    db.commit()

    row = db.execute("SELECT * FROM task WHERE id = ?", (task_id,)).fetchone()
    return jsonify(task_to_dict(row)), 200


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
