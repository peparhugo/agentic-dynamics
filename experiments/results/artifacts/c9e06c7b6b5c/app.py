"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
import os
import base64
import binascii
import hashlib
import hmac
import json
import time
from functools import wraps
from werkzeug.security import check_password_hash
from tasks import send_notification_email
from repositories import TaskRepository, UserAlreadyExistsError, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def rate_limit_key() -> str:
    user_id = current_user_id()
    return f"user:{user_id}" if user_id is not None else f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=REDIS_URL,
    headers_enabled=True,
    in_memory_fallback=["100 per minute"],
)


def user_repository() -> UserRepository:
    return UserRepository(DATABASE)


def task_repository() -> TaskRepository:
    return TaskRepository(DATABASE)


def init_db():
    user_repository().initialize()
    task_repository().initialize()


init_db()


def create_token(user_id: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "exp": int(time.time()) + 86400}

    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()

    unsigned = f"{encode(header)}.{encode(payload)}"
    signature = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def current_user_id() -> int | None:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        encoded_header, encoded_payload, encoded_signature = authorization[7:].split(".")
        unsigned = f"{encoded_header}.{encoded_payload}"
        expected = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected, actual):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4)))
        if payload.get("exp", 0) < time.time() or not isinstance(payload.get("sub"), int):
            return None
        if not user_repository().exists(payload["sub"]):
            return None
        return payload["sub"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = current_user_id()
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    cursor = request.args.get("cursor")
    if cursor is not None:
        try:
            cursor = int(cursor)
            if cursor < 1:
                raise ValueError
        except ValueError:
            return jsonify({"error": "cursor must be a positive integer"}), 400

    try:
        limit = int(request.args.get("limit", 20))
        if limit < 1 or limit > 100:
            raise ValueError
    except ValueError:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    tasks, total, has_more = task_repository().list_for_owner_page(g.user_id, cursor, limit)
    next_cursor = str(tasks[-1]["id"]) if has_more else None
    return jsonify({"data": tasks, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    title = data.get("title", "")
    if not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository().create_task(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repository().get_for_owner(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    existing_task = task_repository().get_for_owner(task_id, g.user_id)
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    if not data or not ("title" in data or "status" in data):
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and (not isinstance(data["status"], str) or not data["status"].strip()):
        return jsonify({"error": "status must be a non-empty string"}), 400
    task = task_repository().update_for_owner(
        task_id, g.user_id,
        title=data.get("title", None).strip() if "title" in data else None,
        status=data.get("status"),
    )
    if existing_task["status"] != "completed" and task["status"] == "completed":
        user_email = user_repository().get_email(g.user_id)
        if user_email is not None:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        return jsonify({"error": "username and password are required"}), 400
    username, password = data["username"].strip(), data["password"]
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    users = user_repository()
    if users.find_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    try:
        user = users.create_user(username, password)
    except UserAlreadyExistsError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        return jsonify({"error": "invalid credentials"}), 401
    user = user_repository().find_by_username(data["username"])
    if user is None or not check_password_hash(user["password_hash"], data["password"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(error):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    retry_after = error.get_response().headers.get("Retry-After")
    if retry_after:
        response.headers["Retry-After"] = retry_after
    return response


if __name__ == "__main__":
    app.run(debug=True)
