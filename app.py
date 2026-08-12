"""Flask API for managing authenticated users and their tasks."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import sqlite3
import logging

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from tasks import send_notification_email


app = Flask(__name__)
logger = logging.getLogger(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the schema and migrate databases created by older versions."""
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            # Nullable keeps legacy task rows readable while new rows are owned.
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        conn.commit()


def _encode_part(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_part(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(json.dumps({
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    }, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode_part(signature)}"


def get_authenticated_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}".encode("ascii")
        expected = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
        if not hmac.compare_digest(_decode_part(signature), expected):
            return None
        claims = json.loads(_decode_part(payload))
        if claims.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        if claims.get("sub") is None:
            return None
        with get_db() as conn:
            return conn.execute("SELECT * FROM users WHERE id = ?", (claims["sub"],)).fetchone()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeError):
        return None


@app.before_request
def authenticate_tasks():
    if request.path.startswith("/tasks"):
        user = get_authenticated_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user = user


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            conn.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


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
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_task(task_id, owner_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
        return dict(row) if row else None


def fetch_task(task_id, owner_id=None):
    """Compatibility alias for callers that use the older helper name."""
    if owner_id is None:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None
    return get_task(task_id, owner_id)


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
        params.extend([task_id, owner_id])
        with get_db() as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params)
            conn.commit()
    return get_task(task_id, owner_id)


@app.get("/tasks")
def list_tasks():
    return jsonify(get_tasks(g.user["id"]))


@app.post("/tasks")
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title") if isinstance(data, dict) else None
    if isinstance(title, str):
        title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title, g.user["id"])), 201


@app.get("/tasks/<int:task_id>")
def show_task(task_id):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    previous_task = get_task(task_id, g.user["id"])
    task = update_task(task_id, g.user["id"], data.get("title"), data.get("status"))
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        try:
            send_notification_email.delay(g.user["username"], task["title"])
        except Exception:
            # A broker outage should not turn a successful task update into an API error.
            logger.exception("Unable to queue completion notification for task %s", task_id)
    return jsonify(task)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
