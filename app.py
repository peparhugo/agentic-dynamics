"""A small SQLite-backed task management API with JWT authentication."""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_LIFETIME = 24 * 60 * 60


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the schema and add new columns to databases from older versions."""
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " username TEXT NOT NULL UNIQUE,"
            " password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " title TEXT NOT NULL,"
            " status TEXT NOT NULL DEFAULT 'pending',"
            " created_at TEXT NOT NULL"
            ")"
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            # Existing tasks remain intact; they have no owner and are not exposed
            # to newly authenticated users.
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def make_token(user_id):
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({"sub": user_id, "exp": int(time.time()) + JWT_LIFETIME}, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}".encode()
    signature = _encode(hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def get_current_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        header, payload, signature = authorization[7:].split(".")
        unsigned = f"{header}.{payload}".encode()
        expected = _encode(hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_decode(payload))
        token_header = json.loads(_decode(header))
        if token_header != {"alg": "HS256", "typ": "JWT"}:
            return None
        if claims.get("exp", 0) <= time.time() or not isinstance(claims.get("sub"), int) or isinstance(claims.get("sub"), bool):
            return None
        with get_db() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (claims["sub"],)).fetchone()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def create_task(title, owner_id):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone())


def get_tasks(owner_id):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)).fetchall()
        return [dict(row) for row in rows]


def get_task(task_id, owner_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)).fetchone()
        return dict(row) if row else None


def update_task(task_id, owner_id, title=None, status=None):
    if get_task(task_id, owner_id) is None:
        return None
    updates, params = [], []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if updates:
        params.extend((task_id, owner_id))
        with get_db() as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params)
            conn.commit()
    return get_task(task_id, owner_id)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username.strip(), generate_password_hash(password)),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": cursor.lastrowid, "username": username.strip()}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (data.get("username"),)).fetchone() if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": make_token(user["id"])})


@app.get("/tasks")
@authenticated
def list_tasks():
    return jsonify(get_tasks(g.user["id"]))


@app.post("/tasks")
@authenticated
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title") if isinstance(data, dict) else None
    title = title.strip() if isinstance(title, str) else ""
    if not title:
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title, g.user["id"])), 201


@app.get("/tasks/<int:task_id>")
@authenticated
def show_task(task_id):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@authenticated
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    task = update_task(task_id, g.user["id"], data.get("title", "").strip() if "title" in data else None, data.get("status"))
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
