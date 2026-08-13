"""A small Flask API for managing per-user tasks."""

import base64
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import hmac
import json
import os

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import (
    DuplicateUsernameError,
    TaskRepository,
    UserRepository,
    connect_database,
)


app = Flask(__name__)
app.config.update(
    JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-secret-change-me"),
    JWT_EXPIRATION_SECONDS=3600,
    RATELIMIT_STORAGE_URI=os.environ.get(
        "RATELIMIT_STORAGE_URI", "redis://localhost:6379/1"
    ),
    RATELIMIT_HEADERS_ENABLED=True,
)

DATABASE = os.environ.get("DATABASE", "todos.db")


def get_db():
    return connect_database(DATABASE)


user_repository = UserRepository(get_db)
task_repository = TaskRepository(get_db)


def rate_limit_key() -> str:
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and token.strip():
        try:
            return f"user:{decode_token(token.strip())}"
        except ValueError:
            pass
    return f"address:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
)


def init_db():
    """Create the schema and migrate task databases created before authentication."""
    user_repository.initialize_schema()
    task_repository.initialize_schema()


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    header = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=app.config["JWT_EXPIRATION_SECONDS"]
    )
    payload = _base64url_encode(
        json.dumps(
            {"sub": user_id, "exp": int(expires_at.timestamp())}, separators=(",", ":")
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), signing_input, hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{_base64url_encode(signature)}"


def decode_token(token: str) -> int:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        supplied_signature = _base64url_decode(signature_part)
        expected_signature = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), signing_input, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid signature")

        header = json.loads(_base64url_decode(header_part))
        payload = json.loads(_base64url_decode(payload_part))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            raise ValueError("invalid header")
        if not isinstance(payload.get("exp"), int):
            raise ValueError("invalid expiry")
        if payload["exp"] <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired token")
        user_id = payload.get("sub")
        if not isinstance(user_id, int) or isinstance(user_id, bool):
            raise ValueError("invalid subject")
        return user_id
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid token") from None


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token.strip():
            return jsonify({"error": "authentication required"}), 401

        try:
            user_id = decode_token(token.strip())
        except ValueError:
            return jsonify({"error": "invalid token"}), 401

        user = user_repository.get_by_id(user_id)
        if user is None:
            return jsonify({"error": "invalid token"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400

    try:
        user = user_repository.create_user(
            username.strip(), generate_password_hash(password)
        )
    except DuplicateUsernameError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid username or password"}), 401

    user = user_repository.get_by_username(username.strip())
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks():
    cursor_value = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        cursor = int(cursor_value) if cursor_value is not None else None
        limit = int(limit_value)
    except ValueError:
        return jsonify({"error": "cursor and limit must be integers"}), 400
    if cursor is not None and cursor <= 0:
        return jsonify({"error": "cursor must be a positive integer"}), 400
    if limit <= 0 or limit > 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    tasks, total = task_repository.list_for_owner(g.user_id, limit, cursor)
    has_next_page = len(tasks) > limit
    data = tasks[:limit]
    next_cursor = str(data[-1]["id"]) if has_next_page else None
    return jsonify({"data": data, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@auth_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create_for_owner(title.strip(), g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def show_task(task_id: int):
    task = task_repository.get_for_owner(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if "title" in data and (
        not isinstance(data["title"], str) or not data["title"].strip()
    ):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    previous_task = task_repository.get_for_owner(task_id, g.user_id)
    task = task_repository.update_for_owner(
        task_id,
        g.user_id,
        title=data["title"].strip() if "title" in data else None,
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        previous_task["status"] != "completed"
        and task["status"] == "completed"
    ):
        owner = user_repository.get_by_id(g.user_id)
        send_notification_email.delay(owner["username"], task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
