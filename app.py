"""Flask API for managing authenticated users' tasks in SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/2")


def get_db() -> sqlite3.Connection:
    """Return a connection configured to expose rows by column name."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the schema and safely add ownership to existing task databases."""
    UserRepository(get_db).initialize()
    TaskRepository(get_db).initialize()


def encode_token(user_id: int) -> str:
    """Create a signed, expiring JWT for a user."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    }
    header_part = base64.urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode()).rstrip(b"=")
    payload_part = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signing_input = header_part + b"." + payload_part
    signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def decode_token(token: str) -> int | None:
    """Return the authenticated user ID if the JWT is valid and current."""
    try:
        header_part, payload_part, signature_part = token.encode().split(b".")
        signing_input = header_part + b"." + payload_part
        expected_signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(signature_part + b"=" * (-len(signature_part) % 4))
        payload = json.loads(base64.urlsafe_b64decode(payload_part + b"=" * (-len(payload_part) % 4)))
        if not hmac.compare_digest(signature, expected_signature) or payload["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return payload["sub"] if isinstance(payload["sub"], int) else None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def rate_limit_key() -> str:
    """Rate-limit authenticated requests by user and auth requests by client."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    user_id = decode_token(token) if scheme == "Bearer" and token else None
    return f"user:{user_id}" if user_id is not None else f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=REDIS_URL,
    headers_enabled=True,
)


def require_auth(view):
    """Require a valid bearer token and pass its user ID to the route."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = decode_token(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


def task_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_task(task_id: int, owner_id: int) -> sqlite3.Row | None:
    return TaskRepository(get_db).get_for_owner(task_id, owner_id)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    email = data.get("email") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400

    try:
        user_id = UserRepository(get_db).create_user(
            username.strip(),
            email.strip() if isinstance(email, str) else None,
            generate_password_hash(password),
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username.strip()}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "username and password are required"}), 400

    user = UserRepository(get_db).get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": encode_token(user["id"])})


@app.post("/tasks")
@require_auth
def create_task(owner_id: int):
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    created_at = datetime.now(timezone.utc).isoformat()
    task_id = TaskRepository(get_db).create_for_owner(title.strip(), created_at, owner_id)

    return jsonify(task_dict(get_task(task_id, owner_id))), 201


@app.get("/tasks")
@require_auth
def list_tasks(owner_id: int):
    cursor = request.args.get("cursor")
    limit = request.args.get("limit", default=20, type=int)
    if cursor is not None:
        try:
            cursor_id = int(cursor)
        except ValueError:
            return jsonify({"error": "cursor must be a positive integer"}), 400
        if cursor_id < 1:
            return jsonify({"error": "cursor must be a positive integer"}), 400
    else:
        cursor_id = None
    if limit is None or not 1 <= limit <= 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    rows, total = TaskRepository(get_db).list_page_for_owner(owner_id, cursor_id, limit)
    has_next_page = len(rows) > limit
    page = rows[:limit]
    return jsonify(
        {
            "data": [task_dict(row) for row in page],
            "next_cursor": str(page[-1]["id"]) if has_next_page else None,
            "total": total,
        }
    )


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(owner_id: int, task_id: int):
    task = get_task(task_id, owner_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_dict(task))


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(owner_id: int, task_id: int):
    task = get_task(task_id, owner_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not any(key in data for key in ("title", "status")):
        return jsonify({"error": "title or status is required"}), 400

    title = task["title"]
    status = task["status"]
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title is required"}), 400
        title = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status is required"}), 400
        status = data["status"].strip()

    TaskRepository(get_db).update_for_owner(task_id, owner_id, title, status)
    owner_email = UserRepository(get_db).get_email(owner_id)
    if task["status"] != "completed" and status == "completed" and owner_email:
        send_notification_email.delay(owner_email, title)
    return jsonify(task_dict(get_task(task_id, owner_id)))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
