"""
Flask Todo API

A single-file Flask app with clean structure: routes, error handling.
Data access is handled by the repository layer; routes never touch SQL directly.
Uses SQLite for storage and initializes the schema on startup.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import os
import jwt

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import redis as redis_lib

from celery_app import send_notification_email
from repositories import (
    TaskRepository,
    UserRepository,
    init_db,
    check_password,
)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

task_repository = TaskRepository()
user_repository = UserRepository()


# ── Auth helpers ─────────────────────────────────────────────


def create_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload.get("user_id")
    except jwt.PyJWTError:
        return None


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        user_id = decode_token(auth[7:].strip())
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user_id = user_id
        return fn(*args, **kwargs)

    return wrapper


# ── Rate limiting ─────────────────────────────────────────────


def rate_limit_identifier() -> str:
    """Key each authenticated user by their id; anonymous callers by IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        user_id = decode_token(auth[7:].strip())
        if user_id is not None:
            return f"user:{user_id}"
    return get_remote_address()


RATE_LIMIT_STORAGE_URI = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Namespace rate limit keys by this codebase so independent environments
# sharing a Redis instance do not interfere with one another's counters.
_RATE_LIMIT_NAMESPACE = hashlib.md5(
    os.path.dirname(os.path.abspath(__file__)).encode()
).hexdigest()[:12]

limiter = Limiter(
    key_func=rate_limit_identifier,
    app=app,
    application_limits=["100 per minute"],
    storage_uri=RATE_LIMIT_STORAGE_URI,
    headers_enabled=True,
    key_prefix=f"task_api:{_RATE_LIMIT_NAMESPACE}",
)


def reset_rate_limits() -> None:
    """Clear this app's rate limit counters (and only this app's)."""
    client = redis_lib.Redis.from_url(RATE_LIMIT_STORAGE_URI)
    prefix = f"LIMITS:LIMITER/task_api:{_RATE_LIMIT_NAMESPACE}"
    for key in client.scan_iter(match=f"{prefix}*", count=1000):
        client.delete(key)


# ── Routes ─────────────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repository.get_by_username(username) is not None:
        return jsonify({"error": "username already taken"}), 409
    user = user_repository.create_user(username, password)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repository.get_by_username(username)
    if user is None or not check_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"], user["username"])
    return jsonify({"token": token, "user": {"id": user["id"], "username": user["username"]}})


@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks():
    limit = request.args.get("limit", default=20, type=int)
    if limit is None or limit < 1:
        limit = 20
    limit = min(limit, 100)

    cursor_raw = request.args.get("cursor")
    cursor = None
    if cursor_raw is not None and cursor_raw.strip():
        try:
            cursor = int(cursor_raw)
        except ValueError:
            return jsonify({"error": "invalid cursor"}), 400

    tasks, next_cursor = task_repository.get_tasks(
        g.user_id, limit=limit, cursor=cursor
    )
    total = task_repository.count_tasks(g.user_id)
    return jsonify({"data": tasks, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@auth_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create_task(g.user_id, title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def show_task(task_id: int):
    task = task_repository.get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = task_repository.update_task(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if task["status"] == "completed":
        user = user_repository.get_by_id(task["owner_id"]) or {}
        try:
            send_notification_email.delay(
                user.get("username", ""), task["title"]
            )
        except Exception:
            # Never let a notification failure block or break the API response.
            app.logger.exception("failed to enqueue notification email")
    return jsonify(task)


@app.errorhandler(429)
def rate_limit_exceeded(e):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    return response


init_db()

if __name__ == "__main__":
    app.run(debug=True)
