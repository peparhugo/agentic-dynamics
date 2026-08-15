"""Task management Flask API with SQLite persistence and JWT authentication."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os
import secrets
import sqlite3
import time

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "86400"))

VALID_STATUSES = {"pending", "done"}


def get_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER REFERENCES users(id)
            );
            """
        )
        conn.commit()


def migrate():
    """Add owner_id to a pre-existing tasks table without losing data."""
    with get_db() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
            conn.commit()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def encode_token(user_id):
    payload = {"sub": str(user_id), "exp": int(time.time()) + TOKEN_TTL}
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token):
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing authorization header"}), 401
        token = auth.split(" ", 1)[1].strip()
        user_id = decode_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401
        with get_db() as conn:
            user = conn.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)

    return wrapper


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not password or not isinstance(password, str) or not password.strip():
        return jsonify({"error": "password is required"}), 400
    username = username.strip()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return jsonify({"error": "username already taken"}), 409
        cur = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
    return jsonify({"id": cur.lastrowid, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not isinstance(username, str) or not password or not isinstance(password, str):
        return jsonify({"error": "username and password required"}), 400
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = encode_token(user["id"])
    return jsonify({"token": token, "username": user["username"]})


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    title = title.strip()
    status = data.get("status", "pending")
    if status not in VALID_STATUSES:
        return jsonify({"error": "invalid status"}), 422
    now = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, status, now, g.user_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return jsonify(task_to_dict(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (g.user_id,),
        ).fetchall()
    return jsonify([task_to_dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        title = data.get("title", row["title"])
        status = data.get("status", row["status"])
        if status not in VALID_STATUSES:
            return jsonify({"error": "invalid status"}), 422
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(task_to_dict(row))


init_db()
migrate()


if __name__ == "__main__":
    app.run(debug=True)
