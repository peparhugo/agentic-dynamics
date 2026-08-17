"""Flask task API with password-based registration and JWT authentication."""

import base64
import binascii
from datetime import datetime
from functools import wraps
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_TTL_SECONDS = 3600
VALID_STATUSES = {"pending", "done", "completed"}
STATUS_ERROR = "status must be either 'pending', 'done', or 'completed'"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
            "status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'completed')), "
            "created_at TEXT NOT NULL)"
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()[0]
        if "completed" not in schema:
            conn.execute("ALTER TABLE tasks RENAME TO tasks_old")
            conn.execute(
                "CREATE TABLE tasks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'pending' "
                "CHECK (status IN ('pending', 'done', 'completed')), "
                "created_at TEXT NOT NULL, owner_id INTEGER)"
            )
            conn.execute(
                "INSERT INTO tasks (id, title, status, created_at, owner_id) "
                "SELECT id, title, status, created_at, owner_id FROM tasks_old"
            )
            conn.execute("DROP TABLE tasks_old")
        # Backfill old rows without making the existing database unusable.
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
            ("__legacy__", generate_password_hash(secrets.token_urlsafe(32))),
        )
        conn.execute(
            "UPDATE tasks SET owner_id = (SELECT id FROM users WHERE username = ?) "
            "WHERE owner_id IS NULL",
            ("__legacy__",),
        )


init_db()


def create_user(username, password):
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "username": username}


def find_user(username):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_task(title, owner_id):
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        conn.commit()
    return {"id": cursor.lastrowid, "title": title, "status": "pending", "created_at": now}


def get_tasks(owner_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_task(task_id, owner_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        return dict(row) if row else None


def update_task(task_id, owner_id, title=None, status=None):
    if get_task(task_id, owner_id) is None:
        return None
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(STATUS_ERROR)
    updates, params = [], []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if updates:
        with get_db() as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                params + [task_id, owner_id],
            )
            conn.commit()
    return get_task(task_id, owner_id)


def _b64encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encode_token(user_id):
    def part(value):
        return _b64encode(json.dumps(value, separators=(",", ":")).encode())

    signing_input = f'{part({"alg": "HS256", "typ": "JWT"})}.{part({"sub": str(user_id), "exp": int(time.time()) + JWT_TTL_SECONDS})}'
    signature = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def current_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        header, payload, signature = authorization[7:].split(".")
        expected = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            return None
        claims = json.loads(_b64decode(payload))
        if int(claims["exp"]) <= int(time.time()):
            return None
        user_id = int(claims["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        g.user = current_user()
        if g.user is None:
            return jsonify({"error": "invalid or missing token"}), 401
        return view(*args, **kwargs)
    return wrapped


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        user = create_user(username, password)
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    username, password = data.get("username"), data.get("password")
    user = find_user(username) if isinstance(username, str) and isinstance(password, str) else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": encode_token(user["id"])})


@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks():
    return jsonify(get_tasks(g.user["id"]))


@app.route("/tasks", methods=["POST"])
@auth_required
def add_task():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        return jsonify({"error": STATUS_ERROR}), 422
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title.strip(), g.user["id"])), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def show_task(task_id):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    status, title = data.get("status"), data.get("title")
    if status is not None and status not in VALID_STATUSES:
        return jsonify({"error": STATUS_ERROR}), 422
    if title is not None and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    previous_task = get_task(task_id, g.user["id"])
    task = update_task(task_id, g.user["id"], title.strip() if isinstance(title, str) else title, status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.user["username"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    app.run(debug=True)
