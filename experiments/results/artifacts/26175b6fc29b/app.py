"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from functools import wraps

import jwt
from flask import Flask, request, jsonify, g
from datetime import timedelta, timezone, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import os

from notifications import send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 60

RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


def rate_limit_key() -> str:
    """Key by authenticated user when a valid token is present, else by IP.

    This lets a single limit definition cover both authenticated task
    endpoints and the unauthenticated auth endpoints (which have no user
    to key on yet).
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return f"user:{payload['sub']}"
        except jwt.PyJWTError:
            pass
    return get_remote_address()


limiter = Limiter(
    app=app,
    key_func=rate_limit_key,
    storage_uri=RATELIMIT_STORAGE_URI,
    default_limits=["100 per minute"],
    headers_enabled=True,
)


@app.errorhandler(429)
def ratelimit_handler(e):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    return response


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
            "  owner_id INTEGER"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        # Migration: existing databases created before owner_id existed won't
        # have the column, and existing rows will have owner_id = NULL.
        existing_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "owner_id" not in existing_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        # Migration: existing databases created before email existed won't
        # have the column, and existing rows will have email = NULL.
        existing_user_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "email" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


# ── Repositories ──────────────────────────────────────────────
# `get_db` is passed by reference (not called here) so each repository
# always opens connections against the current DATABASE, even if it is
# reassigned later (e.g. by tests).

user_repository = UserRepository(get_db)
task_repository = TaskRepository(get_db)


def get_user_by_username(username: str) -> dict | None:
    """Kept as a module-level function for backwards compatibility."""
    return user_repository.find_by_username(username)


# ── Auth helpers ──────────────────────────────────────────────

def generate_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError:
            return jsonify({"error": "missing or invalid token"}), 401
        user = user_repository.find_by_id(payload["sub"])
        if user is None:
            return jsonify({"error": "missing or invalid token"}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


# ── Auth routes ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = (data.get("email") or "").strip() or None
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if get_user_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    email = email or f"{username}@example.com"
    user = user_repository.create(
        username=username,
        password_hash=generate_password_hash(password),
        email=email,
    )
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token})


# ── Task routes ───────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    limit_raw = request.args.get("limit")
    if limit_raw is None:
        limit = DEFAULT_PAGE_LIMIT
    else:
        try:
            limit = int(limit_raw)
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400
        if limit < 1:
            return jsonify({"error": "limit must be a positive integer"}), 400
    limit = min(limit, MAX_PAGE_LIMIT)

    cursor_raw = request.args.get("cursor")
    cursor = None
    if cursor_raw is not None:
        try:
            cursor = int(cursor_raw)
        except ValueError:
            return jsonify({"error": "cursor must be an integer"}), 400

    tasks, next_cursor = task_repository.list_for_owner_page(g.user["id"], cursor, limit)
    total = task_repository.count_for_owner(g.user["id"])
    return jsonify({"data": tasks, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create(title=title, owner_id=g.user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = task_repository.find_by_id_for_owner(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    previous_task = task_repository.find_by_id_for_owner(task_id, g.user["id"])
    task = task_repository.update(
        task_id,
        g.user["id"],
        title=data.get("title"),
        status=new_status,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if new_status == "completed" and previous_task["status"] != "completed":
        send_notification_email.delay(g.user["email"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
