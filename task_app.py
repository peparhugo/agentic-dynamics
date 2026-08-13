"""
Flask Task Management API with JWT Authentication

Endpoints:
- POST /auth/register — create user (JSON: {username, password, email})
- POST /auth/login — return JWT token (JSON: {username, password})
- POST /tasks — create a task (requires auth)
- GET /tasks — list authenticated user's tasks (requires auth)
- GET /tasks/{id} — get a single task (requires auth)
- PUT /tasks/{id} — update a task (requires auth)
"""

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import sqlite3
import os
import secrets
import logging
from repositories import UserRepository, TokenRepository, TaskRepository

logger = logging.getLogger(__name__)

# Try to import Celery task (optional - may not be available in test environment)
try:
    from tasks_celery import send_notification_email
except Exception as e:
    logger.debug(f"Celery not available: {e}")
    send_notification_email = None

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "3600"))

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
limiter = Limiter(
    app=app,
    key_func=lambda: _get_user_id(),
    default_limits=["100 per minute"],
    storage_uri=REDIS_URL,
)

user_repo = UserRepository()
token_repo = TokenRepository(TOKEN_TTL)
task_repo = TaskRepository()


def _get_user_id():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        user = get_user_from_token(token)
        if user:
            return f"user_{user['id']}"
    return get_remote_address()


def init_db():
    db_path = os.environ.get("DATABASE", "tasks.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)


# ── Auth Utilities ──────────────────────────────────────────────


def create_token(user_id: int) -> str:
    return token_repo.create(user_id)


def get_user_from_token(token: str) -> dict | None:
    return token_repo.read(token)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing authorization header"}), 401
        token = auth.split(" ", 1)[1]
        user = get_user_from_token(token)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        return f(user, *args, **kwargs)
    return decorated


# ── Auth Endpoints ──────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
@limiter.limit("100 per minute")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    if user_repo.username_exists(username):
        return jsonify({"error": "username already taken"}), 409
    user_repo.create(username, password, email)
    return jsonify({"message": "user registered", "username": username}), 201


@app.route("/auth/login", methods=["POST"])
@limiter.limit("100 per minute")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    user = user_repo.verify_credentials(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"])
    return jsonify({"token": token, "username": user["username"]})


# ── Task Endpoints ─────────────────────────────────────────────


@app.route("/tasks", methods=["POST"])
@limiter.limit("100 per minute")
@require_auth
def create_task(user: dict):
    data = request.get_json(silent=True) or {}
    title = data.get("title")

    if title is None:
        return jsonify({"error": "title is required"}), 400

    title = str(title).strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    task = task_repo.create(user["id"], title)
    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
@limiter.limit("100 per minute")
@require_auth
def list_tasks(user: dict):
    cursor = request.args.get("cursor", type=int, default=None)
    limit = request.args.get("limit", type=int, default=20)
    result = task_repo.read_paginated(user["id"], cursor=cursor, limit=limit)
    return jsonify(result)


@app.route("/tasks/<int:task_id>", methods=["GET"])
@limiter.limit("100 per minute")
@require_auth
def get_task(user: dict, task_id):
    task = task_repo.read(task_id, user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@limiter.limit("100 per minute")
@require_auth
def update_task(user: dict, task_id):
    data = request.get_json(silent=True) or {}

    old_task = task_repo.read(task_id, user["id"])
    if old_task is None:
        return jsonify({"error": "task not found"}), 404

    old_status = old_task["status"]
    title = data.get("title")
    status = data.get("status")

    if title is not None:
        title = str(title).strip()
    if status is not None:
        status = str(status).strip()

    if title is None and status is None:
        return jsonify(old_task)

    updated_task = task_repo.update(task_id, user["id"], title, status)

    if updated_task is None:
        return jsonify({"error": "task not found"}), 404

    new_status = updated_task["status"]
    task_title = updated_task["title"]

    if status is not None and old_status != "completed" and new_status == "completed":
        if user.get("email") and send_notification_email:
            try:
                send_notification_email.delay(user["email"], task_title)
            except Exception as e:
                logger.warning(f"Failed to queue email notification: {e}")

    return jsonify(updated_task)


@app.route("/health", methods=["GET"])
@limiter.limit("100 per minute")
def health():
    return jsonify({"status": "ok"})


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "rate limit exceeded"}), 429


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
