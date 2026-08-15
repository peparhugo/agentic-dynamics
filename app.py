"""Flask task management API with SQLite persistence and JWT authentication."""

import os
import time
import sqlite3
from functools import wraps

import jwt
from flask import Flask, g, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Migration: add owner_id to existing tasks table without breaking data.
    columns = _table_columns(conn, "tasks")
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()

    conn.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization")
        if not auth:
            return jsonify({"error": "missing authorization header"}), 401
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "invalid authorization header"}), 401
        token = parts[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = int(payload["sub"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return jsonify({"error": "invalid token"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)

    return wrapper


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or not str(username).strip():
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400
    username = str(username).strip()

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing is not None:
        conn.close()
        return jsonify({"error": "username already exists"}), 409

    password_hash = generate_password_hash(password)
    cur = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    token = jwt.encode(
        {"sub": str(row["id"]), "iat": int(time.time())},
        SECRET_KEY,
        algorithm="HS256",
    )
    return jsonify({"token": token})


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    now = int(time.time())
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
        (title, now, g.user_id),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return jsonify(
        {"id": task_id, "title": title, "status": "pending", "created_at": now}
    ), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
        (g.user_id,),
    ).fetchall()
    conn.close()
    return jsonify([task_to_dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.user_id)
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.user_id)
    ).fetchone()
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
