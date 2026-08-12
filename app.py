"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from functools import wraps
import jwt
from flask import Flask, request, jsonify, g
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
import sqlite3
import os
import time
from werkzeug.security import check_password_hash, generate_password_hash
from notifications import send_notification_email
from repositories import TaskRepository, UserRepository, initialize_database

app = Flask(__name__)
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_SECONDS"] = 3600
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
    "REDIS_URL", "redis://localhost:6379/0"
)


def rate_limit_key() -> str:
    """Use the authenticated user when possible, otherwise the client address."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        try:
            payload = jwt.decode(
                header[7:], app.config["JWT_SECRET"], algorithms=["HS256"]
            )
            return f"user:{payload['sub']}"
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            pass
    return f"ip:{request.remote_addr or 'unknown'}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    headers_enabled=True,
    retry_after="delta-seconds",
    in_memory_fallback_enabled=True,
)

DATABASE = os.environ.get("DATABASE", ":memory:")
_connection = sqlite3.connect(DATABASE, check_same_thread=False)
_connection.row_factory = sqlite3.Row


def get_db():
    return _connection


def init_db():
    initialize_database(get_db())


# ── Models ────────────────────────────────────────────────────

def user_repository() -> UserRepository:
    return UserRepository(get_db())


def create_user(username: str, password: str, email: str | None = None) -> dict:
    return user_repository().create_user(
        username, generate_password_hash(password), email or username
    )


def find_user(username: str):
    return user_repository().find_by_username(username)


def create_token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + app.config["JWT_EXPIRATION_SECONDS"]},
        app.config["JWT_SECRET"],
        algorithm="HS256",
    )


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "authorization required"}), 401
        try:
            payload = jwt.decode(
                header[7:], app.config["JWT_SECRET"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid token"}), 401
        user = user_repository().find_by_id(user_id)
        if user is None:
            return jsonify({"error": "invalid token"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def task_repository() -> TaskRepository:
    return TaskRepository(get_db())


def create_task(title: str, owner_id: int) -> dict:
    return task_repository().create_task(title, owner_id)


def get_tasks(owner_id: int):
    return task_repository().list_for_owner(owner_id)


def get_task_page(owner_id: int, cursor: int | None, limit: int):
    return task_repository().list_page_for_owner(owner_id, cursor, limit)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return task_repository().find_for_owner(task_id, owner_id)


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    return task_repository().update_for_owner(task_id, owner_id, title, status)


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    if user_repository().find_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    email = data.get("email")
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a nonblank string"}), 400
    return jsonify(
        user_repository().create_user(
            username,
            generate_password_hash(password),
            email.strip() if email else username,
        )
    ), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    user = find_user(username) if isinstance(username, str) else None
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.errorhandler(RateLimitExceeded)
def rate_limit_exceeded(error):
    return jsonify({"error": "rate limit exceeded"}), 429

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    raw_cursor = request.args.get("cursor")
    raw_limit = request.args.get("limit", "20")
    try:
        cursor = int(raw_cursor) if raw_cursor is not None else None
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return jsonify({"error": "cursor and limit must be integers"}), 400
    if cursor is not None and cursor <= 0:
        return jsonify({"error": "cursor must be a positive integer"}), 400
    if limit < 1 or limit > 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    tasks, has_more, total = get_task_page(g.current_user["id"], cursor, limit)
    return jsonify({
        "data": tasks,
        "next_cursor": str(tasks[-1]["id"]) if has_more else None,
        "total": total,
    })


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str):
        title = ""
    title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository().create_task(title, g.current_user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    existing_task = get_task(task_id, g.current_user["id"])
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404
    task = update_task(
        task_id, g.current_user["id"],
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if existing_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.current_user["email"] or g.current_user["username"], task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
