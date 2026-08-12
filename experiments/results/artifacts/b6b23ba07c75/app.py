"""Flask API for managing authenticated users and their tasks."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import logging

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from tasks import send_notification_email
from repositories import DuplicateUserError, TaskRepository, UserRepository, initialize_database


app = Flask(__name__)
logger = logging.getLogger(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24
RATE_LIMIT = "100 per minute"


def rate_limit_key():
    """Use the authenticated user when available, including for task routes."""
    user = get_authenticated_user()
    identity = f"user:{user['id']}" if user else f"ip:{get_remote_address()}"
    return f"{DATABASE}:{identity}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=[RATE_LIMIT],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", os.environ.get("REDIS_URL", "redis://localhost:6379/0")),
    headers_enabled=True,
)


def get_db():
    return UserRepository(DATABASE).connection()


def init_db():
    """Create the schema and migrate databases created by older versions."""
    initialize_database(DATABASE)


@app.errorhandler(429)
def rate_limit_exceeded(error):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    if error.retry_after is not None:
        response.headers["Retry-After"] = str(error.retry_after)
    return response


def _encode_part(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_part(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(json.dumps({
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    }, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode_part(signature)}"


def get_authenticated_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}".encode("ascii")
        expected = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
        if not hmac.compare_digest(_decode_part(signature), expected):
            return None
        claims = json.loads(_decode_part(payload))
        if claims.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        if claims.get("sub") is None:
            return None
        return UserRepository(DATABASE).get(claims["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeError):
        return None


@app.before_request
def authenticate_tasks():
    if request.path.startswith("/tasks"):
        user = get_authenticated_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user = user


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        user = UserRepository(DATABASE).create({
            "username": username,
            "password_hash": generate_password_hash(password),
        })
    except DuplicateUserError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": username}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    user = UserRepository(DATABASE).find_by_username(username)
    if not user or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


def create_task(title, owner_id):
    now = datetime.now(timezone.utc).isoformat()
    return TaskRepository(DATABASE).create({
        "title": title, "status": "pending", "created_at": now, "owner_id": owner_id,
    })


def get_tasks(owner_id):
    return TaskRepository(DATABASE).for_owner(owner_id)


def get_task(task_id, owner_id):
    return TaskRepository(DATABASE).get_for_owner(task_id, owner_id)


def fetch_task(task_id, owner_id=None):
    """Compatibility alias for callers that use the older helper name."""
    if owner_id is None:
        return TaskRepository(DATABASE).get_any(task_id)
    return get_task(task_id, owner_id)


def update_task(task_id, owner_id, title=None, status=None):
    updates = {}
    if title is not None:
        updates["title"] = title
    if status is not None:
        updates["status"] = status
    return TaskRepository(DATABASE).update_for_owner(task_id, owner_id, updates)


@app.get("/tasks")
def list_tasks():
    cursor = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        limit = int(limit_value)
        if limit < 1 or limit > 100:
            raise ValueError
        if cursor is not None:
            cursor = int(cursor)
            if cursor < 1:
                raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "cursor must be a positive integer and limit must be between 1 and 100"}), 400

    data, next_cursor, total = TaskRepository(DATABASE).page_for_owner(
        g.user["id"], cursor, limit
    )
    return jsonify({"data": data, "next_cursor": next_cursor, "total": total})


@app.post("/tasks")
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title") if isinstance(data, dict) else None
    if isinstance(title, str):
        title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title, g.user["id"])), 201


@app.get("/tasks/<int:task_id>")
def show_task(task_id):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        data = {}
    previous_task = get_task(task_id, g.user["id"])
    task = update_task(task_id, g.user["id"], data.get("title"), data.get("status"))
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        try:
            send_notification_email.delay(g.user["username"], task["title"])
        except Exception:
            # A broker outage should not turn a successful task update into an API error.
            logger.exception("Unable to queue completion notification for task %s", task_id)
    return jsonify(task)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
