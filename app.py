"""Flask API for managing tasks stored in SQLite."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import sqlite3
from functools import wraps

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository, initialize_database


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "todos.db")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_HOURS"] = 24
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0")
app.config["RATELIMIT_DEFAULT"] = "100 per minute"
app.config["RATELIMIT_HEADERS_ENABLED"] = True


def get_db() -> sqlite3.Connection:
    """Create a SQLite connection configured to return mapping-like rows."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


task_repository = TaskRepository(get_db)
user_repository = UserRepository(get_db)


def init_db() -> None:
    """Create application tables and migrate existing task databases."""
    initialize_database(get_db)


def encode_token(user_id: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"])).timestamp()
        ),
    }
    encoded_header = base64.urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode()
    ).rstrip(b"=")
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signing_input = encoded_header + b"." + encoded_payload
    signature = hmac.new(
        app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
    ).digest()
    return (signing_input + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def decode_token(token: str) -> int | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}".encode()
        expected_signature = hmac.new(
            app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
        ).digest()
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, int) or payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return user_id
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


@app.before_request
def identify_rate_limit_client() -> None:
    """Use a token's subject when available, otherwise isolate anonymous requests by IP."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    g.authenticated_user_id = decode_token(token) if scheme == "Bearer" and token else None


def rate_limit_key() -> str:
    user_id = g.get("authenticated_user_id")
    return f"user:{user_id}" if user_id is not None else f"ip:{get_remote_address()}"


limiter = Limiter(key_func=rate_limit_key, app=app)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = g.authenticated_user_id
        if user_id is None:
            return jsonify(error="authentication required"), 401
        return view(user_id, *args, **kwargs)

    return wrapped


def get_task(task_id: int, owner_id: int) -> dict | None:
    return task_repository.get_for_owner(task_id, owner_id)


def validate_title(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def validate_credentials(data: object) -> tuple[str, str, str | None] | None:
    if not isinstance(data, dict):
        return None
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return None
    email = data.get("email")
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return None
    return username.strip(), password, email.strip() if email else None


def parse_pagination() -> tuple[int | None, int] | None:
    cursor_value = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        cursor = int(cursor_value) if cursor_value is not None else None
        limit = int(limit_value)
    except ValueError:
        return None
    if (cursor is not None and cursor < 1) or not 1 <= limit <= 100:
        return None
    return cursor, limit


@app.errorhandler(429)
def rate_limit_exceeded(error):
    response = jsonify(error="rate limit exceeded")
    response.status_code = 429
    retry_after = getattr(error, "retry_after", None)
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


@app.post("/auth/register")
def register():
    credentials = validate_credentials(request.get_json(silent=True))
    if credentials is None:
        return jsonify(error="username and password are required"), 400

    username, password, email = credentials
    try:
        user_repository.create(
            {"username": username, "password_hash": generate_password_hash(password), "email": email}
        )
    except sqlite3.IntegrityError:
        return jsonify(error="username already exists"), 409
    return jsonify(username=username), 201


@app.post("/auth/login")
def login():
    credentials = validate_credentials(request.get_json(silent=True))
    if credentials is None:
        return jsonify(error="username and password are required"), 400

    username, password, _ = credentials
    user = user_repository.get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=encode_token(user["id"]))


@app.post("/tasks")
@require_auth
def create_task(user_id: int):
    data = request.get_json(silent=True)
    title = validate_title(data.get("title")) if isinstance(data, dict) else None
    if title is None:
        return jsonify(error="title is required"), 400

    created_at = datetime.now(timezone.utc).isoformat()
    task_id = task_repository.create(
        {"title": title, "created_at": created_at, "owner_id": user_id}
    )

    return jsonify(get_task(task_id, user_id)), 201


@app.get("/tasks")
@require_auth
def list_tasks(user_id: int):
    pagination = parse_pagination()
    if pagination is None:
        return jsonify(error="cursor and limit must be positive integers; limit cannot exceed 100"), 400
    cursor, limit = pagination
    tasks, total = task_repository.list_page_for_owner(user_id, cursor, limit)
    has_more = len(tasks) > limit
    data = tasks[:limit]
    return jsonify(data=data, next_cursor=str(data[-1]["id"]) if has_more else None, total=total)


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(user_id: int, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(user_id: int, task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body is required"), 400

    updates = {}
    if "title" in data:
        title = validate_title(data["title"])
        if title is None:
            return jsonify(error="title must be a non-empty string"), 400
        updates["title"] = title
    if "status" in data:
        if not isinstance(data["status"], str):
            return jsonify(error="status must be a string"), 400
        updates["status"] = data["status"]
    if not updates:
        return jsonify(error="title or status is required"), 400

    notification = None
    existing_task = task_repository.get_notification_details(task_id, user_id)
    if existing_task is None:
        return jsonify(error="task not found"), 404

    task_repository.update_for_owner(task_id, user_id, updates)
    if data.get("status") == "completed" and existing_task["status"] != "completed":
        notification = (
            existing_task["email"] or f"{existing_task['username']}@example.com",
            existing_task["title"],
        )

    if notification:
        send_notification_email.delay(*notification)

    return jsonify(get_task(task_id, user_id))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
