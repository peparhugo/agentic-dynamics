"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import os
from celery import Celery
from flask_limiter import Limiter
from werkzeug.security import check_password_hash, generate_password_hash
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-only-secret")
JWT_EXPIRATION_HOURS = 24
RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/1")
celery = Celery("task_notifications")
celery.config_from_object("celery_config")


@celery.task
def send_notification_email(user_email: str, task_title: str) -> None:
    """Send the completion notification from a Celery worker."""
    app.logger.info("Task '%s' completed; notifying %s", task_title, user_email)


def init_db():
    UserRepository(DATABASE).initialize()
    TaskRepository(DATABASE).initialize()


init_db()


def _encode_segment(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()


def _decode_segment(value: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


def create_token(user_id: int) -> str:
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = _encode_segment({
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    })
    signed = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(
        hmac.new(JWT_SECRET.encode(), signed.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{signed}.{signature}"


def verify_token(token: str) -> int | None:
    try:
        header, payload, signature = token.split(".")
        expected = base64.urlsafe_b64encode(
            hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        claims = _decode_segment(payload)
        if not hmac.compare_digest(signature, expected) or claims["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return int(claims["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def rate_limit_key() -> str:
    """Use a stable user identity when a valid bearer token is supplied."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    user_id = verify_token(token) if scheme == "Bearer" and token else None
    return f"user:{user_id}" if user_id is not None else request.remote_addr or "anonymous"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=RATELIMIT_STORAGE_URI,
    headers_enabled=True,
    # Keep local development and tests usable when the configured Redis service is unavailable.
    in_memory_fallback_enabled=True,
)


@app.errorhandler(429)
def rate_limit_exceeded(error):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    response.headers["Retry-After"] = str(getattr(error, "retry_after", None) or 60)
    return response


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = verify_token(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)
    return wrapped


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    email = data.get("email", username)
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "email must be a non-empty string"}), 400
    user = UserRepository(DATABASE).create_user(
        username.strip(), email.strip(), generate_password_hash(password)
    )
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid username or password"}), 401
    user = UserRepository(DATABASE).get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user["id"])})

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    cursor = request.args.get("cursor")
    try:
        cursor_id = int(cursor) if cursor is not None else None
        if cursor_id is not None and cursor_id < 1:
            raise ValueError
        limit = int(request.args.get("limit", 20))
        if limit < 1:
            raise ValueError
    except ValueError:
        return jsonify({"error": "cursor and limit must be positive integers"}), 400

    tasks, total, has_more = TaskRepository(DATABASE).list_page_for_owner(
        g.user_id, cursor_id, min(limit, 100)
    )
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
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    title = title.strip()
    task = TaskRepository(DATABASE).create({
        "title": title,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "owner_id": g.user_id,
    })
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = TaskRepository(DATABASE).get_for_owner(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400

    task_repository = TaskRepository(DATABASE)
    previous_task = task_repository.get_for_owner(task_id, g.user_id)
    if previous_task is None:
        return jsonify({"error": "task not found"}), 404

    updates = {}
    if title is not None:
        updates["title"] = title.strip()
    if data.get("status") is not None:
        updates["status"] = data["status"]
    task = task_repository.update_for_owner(task_id, g.user_id, updates)
    if previous_task["status"] != "completed" and task["status"] == "completed":
        user = UserRepository(DATABASE).get_by_id(g.user_id)
        send_notification_email.delay(user["email"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    app.run(debug=True)
