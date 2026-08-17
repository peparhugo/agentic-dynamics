"""Flask task API with password-based registration and JWT authentication."""

import base64
import binascii
from datetime import datetime
from functools import wraps
import hashlib
import hmac
import json
import os
import time

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash

from notifications import send_notification_email
from repositories import (
    TaskRepository,
    UserAlreadyExistsError,
    UserRepository,
    initialize_database,
)

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_TTL_SECONDS = 3600
RATE_LIMIT_STORAGE_URI = os.environ.get(
    "RATE_LIMIT_STORAGE_URI", os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)
VALID_STATUSES = {"pending", "done", "completed"}
STATUS_ERROR = "status must be either 'pending', 'done', or 'completed'"


def rate_limit_key():
    """Use the authenticated user as the bucket, or the client IP before login."""
    user = getattr(g, "user", None)
    if user is None:
        user = current_user()
    return f"user:{user['id']}" if user else get_remote_address()


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=RATE_LIMIT_STORAGE_URI,
    headers_enabled=True,
)


def init_db():
    initialize_database(DATABASE)


init_db()


def user_repository():
    return UserRepository(DATABASE)


def task_repository():
    return TaskRepository(DATABASE)


def _b64encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encode_token(user_id):
    def part(value):
        return _b64encode(json.dumps(value, separators=(",", ":")).encode())

    signing_input = f'{part({"alg": "HS256", "typ": "JWT"})}.{part({"sub": str(user_id), "exp": int(time.time()) + JWT_TTL_SECONDS})}'
    signature = hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def current_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        header, payload, signature = authorization[7:].split(".")
        expected = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            return None
        claims = json.loads(_b64decode(payload))
        if int(claims["exp"]) <= int(time.time()):
            return None
        user_id = int(claims["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None
    return user_repository().find_by_id(user_id)


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        g.user = current_user()
        if g.user is None:
            return jsonify({"error": "invalid or missing token"}), 401
        return view(*args, **kwargs)
    return wrapped


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        user = user_repository().create_user(username, password)
    except UserAlreadyExistsError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    username, password = data.get("username"), data.get("password")
    user = user_repository().find_by_username(username) if isinstance(username, str) and isinstance(password, str) else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": encode_token(user["id"])})


@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks():
    raw_limit = request.args.get("limit", "20")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer between 1 and 100"}), 400
    if not 1 <= limit <= 100:
        return jsonify({"error": "limit must be an integer between 1 and 100"}), 400

    raw_cursor = request.args.get("cursor")
    if raw_cursor is None:
        cursor = None
    else:
        try:
            cursor = int(raw_cursor)
        except (TypeError, ValueError):
            return jsonify({"error": "cursor must be an integer"}), 400
        if cursor < 1:
            return jsonify({"error": "cursor must be an integer"}), 400

    tasks, total = task_repository().list_for_owner(g.user["id"], cursor, limit)
    has_next_page = len(tasks) > limit
    tasks = tasks[:limit]
    return jsonify({
        "data": tasks,
        "next_cursor": str(tasks[-1]["id"]) if has_next_page else None,
        "total": total,
    })


@app.route("/tasks", methods=["POST"])
@auth_required
def add_task():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        return jsonify({"error": STATUS_ERROR}), 422
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = task_repository().create_task(title.strip(), g.user["id"], datetime.utcnow().isoformat())
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def show_task(task_id):
    task = task_repository().get_for_owner(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    status, title = data.get("status"), data.get("title")
    if status is not None and status not in VALID_STATUSES:
        return jsonify({"error": STATUS_ERROR}), 422
    if title is not None and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    repository = task_repository()
    previous_task = repository.get_for_owner(task_id, g.user["id"])
    task = repository.update_for_owner(
        task_id, g.user["id"], title.strip() if isinstance(title, str) else title, status
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.user["username"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    app.run(debug=True)
