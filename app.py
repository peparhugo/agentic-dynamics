"""Codebase seed — Minimal Flask Todo API with JWT authentication."""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import jwt
import bcrypt
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from celery_tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key")
JWT_EXPIRATION_HOURS = 24

RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")


def get_rate_limit_key():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)
        if payload:
            return f"user:{payload['user_id']}"
    return get_remote_address()


limiter = Limiter(
    app=app,
    key_func=get_rate_limit_key,
    storage_uri=RATELIMIT_STORAGE_URI,
    default_limits=["100 per minute"],
)


@app.errorhandler(429)
def ratelimit_error(e):
    retry_after = getattr(e, "retry_after", None)
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    if retry_after is not None:
        response.headers["Retry-After"] = str(int(retry_after))
    return response


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


task_repo = TaskRepository(get_db)
user_repo = UserRepository(get_db)


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
    migrate_db()


def migrate_db():
    with get_db() as conn:
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass


# ── Legacy helpers ────────────────────────────────────────────


def _legacy_format_date(ts):
    import re
    return re.sub(r"T", " ", ts)


def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")


# ── Auth helpers ──────────────────────────────────────────────


def generate_token(user):
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "email": user.get("email") or f"{user['username']}@example.com",
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)
        if payload is None:
            return jsonify({"error": "missing or invalid token"}), 401
        request.current_user = payload
        return f(*args, **kwargs)

    return decorated


# ── Backward-compatible model wrappers ────────────────────────


def create_user(username, password, email=None):
    return user_repo.create(username, password, email)


def get_user_by_username(username):
    return user_repo.find_by_username(username)


def verify_password(user, password):
    return user_repo.verify_password(user, password)


def create_task(title, owner_id):
    return task_repo.create(title, owner_id)


def get_tasks(owner_id):
    return task_repo.find_all(owner_id)


def get_task(task_id, owner_id):
    return task_repo.find_by_id(task_id, owner_id)


def fetch_task(task_id, owner_id):
    return task_repo.find_by_id(task_id, owner_id)


def update_task(task_id, owner_id, title=None, status=None):
    return task_repo.update(task_id, owner_id, title, status)


# ── Auth routes ───────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.create(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.find_by_username(username)
    if user is None or not user_repo.verify_password(user, password):
        return jsonify({"error": "invalid username or password"}), 401
    token = generate_token(user)
    return jsonify({"token": token})


# ── Task routes (protected) ───────────────────────────────────


@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    user_id = request.current_user["user_id"]
    cursor = request.args.get("cursor")
    limit = request.args.get("limit", 20, type=int)
    limit = max(1, min(limit, 100))
    data, total, next_cursor = task_repo.find_paginated(
        user_id, cursor=cursor, limit=limit
    )
    return jsonify({"data": data, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    user_id = request.current_user["user_id"]
    task = task_repo.create(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id):
    user_id = request.current_user["user_id"]
    task = task_repo.find_by_id(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    user_id = request.current_user["user_id"]
    new_status = data.get("status")
    prev_task = task_repo.find_by_id(task_id, user_id)
    task = task_repo.update(
        task_id,
        user_id,
        title=data.get("title"),
        status=new_status,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if new_status == "completed" and (
        prev_task is None or prev_task.get("status") != "completed"
    ):
        user_email = request.current_user.get("email")
        send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
