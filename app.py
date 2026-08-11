from flask import Flask, request, jsonify, g
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL"
        ")"
    )
    db.commit()


def create_task(title: str) -> dict:
    now = datetime.utcnow().isoformat()
    db = get_db()
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


def get_tasks():
    db = get_db()
    rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    task = get_task(task_id)
    if task is None:
        return None
    db = get_db()
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
        db.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
        )
        db.commit()
    return get_task(task_id)


@app.route("/tasks", methods=["GET"])
def list_tasks():
    return jsonify(get_tasks())


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
