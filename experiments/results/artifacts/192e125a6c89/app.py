"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, make_response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import sqlite3
import os
import re
import jwt
import bcrypt
from functools import wraps
from celery_config import send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24
RATE_LIMIT_STORAGE = os.environ.get("RATE_LIMIT_STORAGE", "redis://localhost:6379")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _rate_limit_key():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            return f"user:{payload['user_id']}"
    return get_remote_address()


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=["100 per minute"],
    storage_uri=RATE_LIMIT_STORAGE,
)
limiter.init_app(app)


@app.errorhandler(429)
def ratelimit_error(e):
    retry_after = 60
    response = make_response(jsonify({"error": "rate limit exceeded"}), 429)
    response.headers["Retry-After"] = str(retry_after)
    return response


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
    password_hash = hash_password(password)
    return UserRepository(DATABASE).create(username, password_hash)


def get_user_by_username(username: str) -> dict | None:
    return UserRepository(DATABASE).get_by_username(username)


def authenticate_user(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def get_user_by_id(user_id: int) -> dict | None:
    return UserRepository(DATABASE).get_by_id(user_id)


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated


# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


def create_task(title: str, owner_id: int = None) -> dict:
    return TaskRepository(DATABASE).create(title, owner_id)


def get_tasks(owner_id: int = None):
    return TaskRepository(DATABASE).get_all(owner_id)


def get_task(task_id: int, owner_id: int = None) -> dict | None:
    return TaskRepository(DATABASE).get_by_id(task_id, owner_id)


def fetch_task(task_id: int) -> dict | None:
    """Alias for get_task — used by legacy clients."""
    return get_task(task_id)


def update_task(task_id: int, owner_id: int = None, title: str | None = None, status: str | None = None) -> dict | None:
    return TaskRepository(DATABASE).update(task_id, owner_id, title, status)


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
    cursor = request.args.get("cursor", None, type=int)
    limit = request.args.get("limit", 20, type=int)
    limit = min(max(limit, 1), 100)
    items, total = TaskRepository(DATABASE).get_paginated(
        owner_id=request.current_user_id, cursor=cursor, limit=limit
    )
    has_more = len(items) > limit
    if has_more:
        items = items[:limit]
        next_cursor = str(items[-1]["id"]) if items else None
    else:
        next_cursor = None
    return jsonify({"data": items, "next_cursor": next_cursor, "total": total})


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
