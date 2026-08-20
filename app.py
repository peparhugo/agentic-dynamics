"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Extended with JWT authentication and per-user task ownership.

The data access layer has been refactored into the Repository pattern. All
SQLite queries live in ``repositories.py``; route handlers only call
repository methods.
"""

import functools
import os
import sqlite3
import time

import jwt
from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash

from repositories import TaskRepository, UserRepository
from tasks import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-0123456789abcdef")
TOKEN_TTL_SECONDS = 86400
RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")
RATELIMIT_STORAGE_URI = os.environ.get(
    "RATELIMIT_STORAGE_URI", "redis://localhost:6379/0"
)
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
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
            "  owner_id INTEGER"
            ")"
        )
        # Migration: add owner_id to pre-existing tasks tables without data loss.
        columns = [row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


user_repo = UserRepository(get_db)
task_repo = TaskRepository(get_db)


# ── Auth helpers ──────────────────────────────────────────────

def generate_token(user_id: int) -> str:
    payload = {"user_id": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def require_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth.split(" ", 1)[1]
        user_id = decode_token(token)
        if user_id is None or user_repo.get_by_id(user_id) is None:
            return jsonify({"error": "missing or invalid token"}), 401
        g.current_user_id = user_id
        return f(*args, **kwargs)

    return wrapper


def rate_limit_key() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        user_id = decode_token(token)
        if user_id is not None:
            return f"user:{user_id}"
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=RATELIMIT_STORAGE_URI,
    default_limits=[RATE_LIMIT],
    headers_enabled=True,
)
limiter.init_app(app)


# ── Helpers ───────────────────────────────────────────────────

def get_user_email(user: dict) -> str:
    return f"{user['username']}@example.com"


# ── Auth routes ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.create(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = user_repo.get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": generate_token(user["id"])})


# ── Task routes ───────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    limit = request.args.get("limit", default=DEFAULT_PAGE_SIZE, type=int)
    if limit is None or limit < 1:
        limit = DEFAULT_PAGE_SIZE
    limit = min(limit, MAX_PAGE_SIZE)
    cursor = request.args.get("cursor", type=int)
    page = task_repo.get_page(g.current_user_id, cursor=cursor, limit=limit)
    return jsonify(page)


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, g.current_user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repo.get_by_id(task_id, g.current_user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    old_task = task_repo.get_by_id(task_id, g.current_user_id)
    task = task_repo.update(
        task_id,
        g.current_user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if task["status"] == "completed" and old_task["status"] != "completed":
        owner = user_repo.get_by_id(g.current_user_id)
        send_notification_email.delay(get_user_email(owner), task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
