import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email
from repositories import (
    BaseRepository,
    DuplicateUsernameError,
    TaskRepository,
    UserRepository,
)


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "development-secret-change-in-production"
)
app.config["JWT_EXPIRATION_SECONDS"] = 3600
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
    "RATELIMIT_STORAGE_URI", "redis://localhost:6379/1"
)
app.config["RATELIMIT_HEADERS_ENABLED"] = True
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    return BaseRepository.connect(DATABASE)


def init_db():
    BaseRepository.initialize_database(DATABASE)


def task_repository():
    return TaskRepository(DATABASE)


def user_repository():
    return UserRepository(DATABASE)


def rate_limit_key():
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and separator and token:
        user = decode_token(token)
        if user is not None:
            return f"user:{user['id']}"
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=app.config["RATELIMIT_STORAGE_URI"],
)


def _base64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(user_id):
    header = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    now = int(time.time())
    payload = _base64url_encode(
        json.dumps(
            {
                "sub": str(user_id),
                "iat": now,
                "exp": now + app.config["JWT_EXPIRATION_SECONDS"],
            },
            separators=(",", ":"),
        ).encode()
    )
    message = f"{header}.{payload}"
    signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
    ).digest()
    return f"{message}.{_base64url_encode(signature)}"


def decode_token(token):
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        message = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
        ).digest()
        signature = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(signature, expected_signature):
            return None

        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        if not isinstance(header, dict) or not isinstance(payload, dict):
            return None
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return None
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(time.time()):
            return None
        user_id = int(payload["sub"])
    except (
        binascii.Error,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None

    user = user_repository().get_by_id(user_id)
    if user is None:
        return None
    return {"id": user["id"], "username": user["username"]}


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            return jsonify(error="authentication required"), 401

        user = decode_token(token)
        if user is None:
            return jsonify(error="invalid token"), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def create_task(title, owner_id):
    created_at = datetime.now(timezone.utc).isoformat()
    return task_repository().create_for_owner(title, created_at, owner_id)


def get_tasks(owner_id, cursor=None, limit=20):
    repository = task_repository()
    tasks = repository.list_for_owner(owner_id, cursor, limit)
    has_next_page = len(tasks) > limit
    tasks = tasks[:limit]
    return {
        "data": tasks,
        "next_cursor": str(tasks[-1]["id"]) if has_next_page else None,
        "total": repository.count_for_owner(owner_id),
    }


def get_task(task_id, owner_id):
    return task_repository().get_for_owner(task_id, owner_id)


def update_task(task_id, owner_id, title=None, status=None):
    updates = {}
    if title is not None:
        updates["title"] = title
    if status is not None:
        updates["status"] = status
    return task_repository().update_for_owner(task_id, owner_id, **updates)


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def credentials():
    data = json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return None, None
    if not isinstance(password, str) or not password:
        return None, None
    return username.strip(), password


@app.post("/auth/register")
def register():
    username, password = credentials()
    if username is None:
        return jsonify(error="username and password are required"), 400

    try:
        user = user_repository().create_user(
            username, generate_password_hash(password)
        )
    except DuplicateUsernameError:
        return jsonify(error="username already exists"), 409
    return jsonify(id=user["id"], username=username), 201


@app.post("/auth/login")
def login():
    username, password = credentials()
    if username is None:
        return jsonify(error="username and password are required"), 400

    user = user_repository().get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=create_token(user["id"]))


@app.post("/tasks")
@require_auth
def add_task():
    title = json_body().get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400
    return jsonify(create_task(title.strip(), g.current_user["id"])), 201


@app.get("/tasks")
@require_auth
def list_tasks():
    cursor_value = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        cursor = int(cursor_value) if cursor_value is not None else None
        limit = int(limit_value)
    except ValueError:
        return jsonify(error="cursor and limit must be integers"), 400
    if cursor is not None and cursor <= 0:
        return jsonify(error="cursor must be a positive integer"), 400
    if not 1 <= limit <= 100:
        return jsonify(error="limit must be between 1 and 100"), 400
    return jsonify(get_tasks(g.current_user["id"], cursor, limit))


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(task_id):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def edit_task(task_id):
    data = json_body()
    if "title" in data and (
        not isinstance(data["title"], str) or not data["title"].strip()
    ):
        return jsonify(error="title must be a non-empty string"), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify(error="status must be a string"), 400

    previous_task = get_task(task_id, g.current_user["id"])
    if previous_task is None:
        return jsonify(error="task not found"), 404

    task = update_task(
        task_id,
        g.current_user["id"],
        title=data["title"].strip() if "title" in data else None,
        status=data.get("status"),
    )
    if task is None:
        return jsonify(error="task not found"), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.current_user["username"], task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run()
