"""
Codebase seed — Minimal Flask Todo API with JWT authentication.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import jwt

try:
    from celery_config import send_notification_email
except ImportError:
    send_notification_email = None

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded

from repositories.task_repository import TaskRepository
from repositories.user_repository import UserRepository

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
DATABASE = os.environ.get("DATABASE", "todos.db")


def _get_rate_limit_key():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            return str(payload["user_id"])
        except Exception:
            pass
    return get_remote_address()


limiter = Limiter(
    app=app,
    key_func=_get_rate_limit_key,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URL", "redis://localhost:6379"),
    application_limits=[os.environ.get("RATE_LIMIT", "100 per minute")],
)


@app.errorhandler(RateLimitExceeded)
def _ratelimit_handler(e):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    if hasattr(e, 'retry_after'):
        response.headers["Retry-After"] = str(e.retry_after)
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
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT NOT NULL DEFAULT ''"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER,"
            "  FOREIGN KEY (owner_id) REFERENCES users (id)"
            ")"
        )
        _migrate_add_owner_id(conn)
        _migrate_add_email(conn)


def _migrate_add_owner_id(conn):
    cursor = conn.execute("PRAGMA table_info(tasks)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def _migrate_add_email(conn):
    cursor = conn.execute("PRAGMA table_info(users)")
    columns = [row["name"] for row in cursor.fetchall()]
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
        conn.commit()


# ── Auth helpers ────────────────────────────────────────────────

def generate_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user_id = payload["user_id"]
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"error": "missing or invalid token"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Auth Routes ─────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    email = (data.get("email") or "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.create(username, password, email)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    token = generate_token(user["id"])
    return jsonify({"token": token, "user": user}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.find_by_username(username)
    if user is None or not UserRepository.verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid username or password"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token, "user": {"id": user["id"], "username": user["username"]}})


# ── Task Routes ─────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    cursor = request.args.get("cursor", type=int)
    limit = request.args.get("limit", 20, type=int)
    limit = max(1, min(limit, 100))
    result = task_repo.find_all_by_owner_paginated(request.user_id, cursor, limit)
    return jsonify(result)


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, request.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = task_repo.find_by_id_and_owner(task_id, request.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    old_task = task_repo.find_by_id_and_owner(task_id, request.user_id)
    if old_task is None:
        return jsonify({"error": "task not found"}), 404
    old_status = old_task["status"]
    task = task_repo.update(
        task_id,
        request.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    new_status = task["status"]
    if old_status != "completed" and new_status == "completed":
        user = user_repo.find_by_id(request.user_id)
        if user and user.get("email") and send_notification_email:
            send_notification_email.delay(user["email"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
