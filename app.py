"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import re
import jwt
import bcrypt
from functools import wraps
from celery_config import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER DEFAULT NULL REFERENCES users(id)"
            ")"
        )
    _migrate_tasks_add_owner_id()
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )


def _migrate_tasks_add_owner_id():
    with get_db() as conn:
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER DEFAULT NULL REFERENCES users(id)")
        except sqlite3.OperationalError:
            pass


# ── Auth helpers ────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[7:]
        payload = decode_token(token)
        if payload is None:
            return jsonify({"error": "invalid or expired token"}), 401
        request.current_user_id = payload["user_id"]
        return f(*args, **kwargs)
    return decorated


# ── User models ─────────────────────────────────────────────────


def create_user(username: str, password: str) -> dict:
    with get_db() as conn:
        password_hash = hash_password(password)
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username}
        except sqlite3.IntegrityError:
            return None


def get_user_by_username(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def authenticate_user(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated


# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


def create_task(title: str, owner_id: int = None) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }


def get_tasks(owner_id: int = None):
    with get_db() as conn:
        if owner_id is not None:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int = None) -> dict | None:
    with get_db() as conn:
        if owner_id is not None:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id),
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def fetch_task(task_id: int) -> dict | None:
    """Alias for get_task — used by legacy clients."""
    return get_task(task_id)


def update_task(task_id: int, owner_id: int = None, title: str | None = None, status: str | None = None) -> dict | None:
    task = get_task(task_id, owner_id)
    if task is None:
        return None
    with get_db() as conn:
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
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
    return get_task(task_id, owner_id)


# ── Auth Routes ─────────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username:
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400

    user = create_user(username, password)
    if user is None:
        return jsonify({"error": "username already taken"}), 409

    return jsonify({"message": "user created", "user": user}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = authenticate_user(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401

    token = create_token(user["id"])
    return jsonify({"token": token}), 200


# ── Routes ─────────────────────────────────────────────────────


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(owner_id=request.current_user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, owner_id=request.current_user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, owner_id=request.current_user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    previous = get_task(task_id, owner_id=request.current_user_id)
    if previous is None:
        return jsonify({"error": "task not found"}), 404
    task = update_task(
        task_id,
        owner_id=request.current_user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    status = data.get("status")
    if status is not None and status == "completed" and previous.get("status") != "completed":
        user = get_user_by_id(request.current_user_id)
        user_email = f"{user['username']}@example.com" if user else "unknown@example.com"
        try:
            send_notification_email.delay(user_email, task["title"])
        except Exception:
            pass
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
