"""
Codebase seed — Minimal Flask Todo API with JWT authentication.

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.

All database access is isolated behind the Repository pattern (see
repositories.py); route handlers never touch SQL directly.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta, timezone
import os
import time

import bcrypt
import jwt
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from redis.connection import ConnectionPool

from celery_app import send_notification_email
from repositories import BaseRepository, TaskRepository, UserRepository, init_db

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")

user_repo = UserRepository(DATABASE)
task_repo = TaskRepository(DATABASE)


# ── Rate limiting ─────────────────────────────────────────────

def _make_rate_limit_storage():
    """Return a Redis-backed storage config, using fakeredis in tests."""
    if os.environ.get("FAKEREDIS") == "1":
        import fakeredis

        return {
            "storage_uri": REDIS_URL,
            "storage_options": {
                "connection_pool": ConnectionPool(
                    connection_class=fakeredis.FakeRedisConnection,
                    server=fakeredis.FakeServer(),
                )
            },
        }
    return {"storage_uri": REDIS_URL, "storage_options": {}}


def _rate_limit_key() -> str:
    """Key limits by authenticated user id, falling back to client IP."""
    user = get_current_user()
    if user is not None:
        return f"user:{user['id']}"
    return get_remote_address()


_rate_limit_storage = _make_rate_limit_storage()

limiter = Limiter(
    key_func=_rate_limit_key,
    app=app,
    storage_uri=_rate_limit_storage["storage_uri"],
    storage_options=_rate_limit_storage["storage_options"],
    default_limits=[RATE_LIMIT],
)


@app.errorhandler(RateLimitExceeded)
def _rate_limit_error(e: RateLimitExceeded):
    reset_at = getattr(e.limit, "reset_at", None)
    retry_after = 60
    if reset_at is not None:
        try:
            retry_after = max(1, int(reset_at.timestamp() - time.time()))
        except Exception:
            retry_after = 60
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


# ── Auth helpers ───────────────────────────────────────────────

def create_user(username: str, password: str, email: str | None = None) -> dict:
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = user_repo.create(
        username=username, password_hash=password_hash, email=email
    )
    return {"id": user["id"], "username": user["username"]}


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def make_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return user_repo.get_by_id(payload["sub"])


def login_required(f):
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        request.current_user = user
        return f(*args, **kwargs)

    wrapper.__name__ = f.__name__
    return wrapper


# ── Auth routes ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username:
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400
    if user_repo.get_by_username(username) is not None:
        return jsonify({"error": "username already taken"}), 409
    email = data.get("email")
    user = create_user(username, password, email)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    user = user_repo.get_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": make_token(user)})


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    try:
        limit = int(request.args.get("limit", 20))
        cursor_raw = request.args.get("cursor")
        cursor = int(cursor_raw) if cursor_raw else None
    except (TypeError, ValueError):
        return jsonify({"error": "invalid pagination parameters"}), 400
    if limit < 1:
        return jsonify({"error": "limit must be a positive integer"}), 400
    limit = min(limit, 100)
    total, items, has_more = task_repo.list_for_owner(
        request.current_user["id"], cursor=cursor, limit=limit
    )
    next_cursor = str(items[-1]["id"]) if has_more and items else None
    return jsonify({"data": items, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, request.current_user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = task_repo.get_for_owner(task_id, request.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    owner_id = request.current_user["id"]
    before = task_repo.get_for_owner(task_id, owner_id)
    task = task_repo.update(
        task_id,
        owner_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        before is not None
        and before["status"] != "completed"
        and task["status"] == "completed"
    ):
        user_email = request.current_user.get("email") or request.current_user["username"]
        send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
