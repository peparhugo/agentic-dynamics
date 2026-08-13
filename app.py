"""Flask API for managing per-user tasks."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import hmac
import json
import os
from threading import Lock
from typing import Any, Callable, TypeVar

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash

from notification_tasks import send_notification_email
from repositories import BaseRepository, Task, TaskRepository, User, UserRepository


app = Flask(__name__)
app.config.update(
    JWT_SECRET=os.environ.get("JWT_SECRET", "development-only-secret"),
    JWT_TTL_SECONDS=3600,
    RATELIMIT_STORAGE_URI=os.environ.get(
        "RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/1"
    ),
)


_store: dict[str, Any] = {}
_store_lock = Lock()
F = TypeVar("F", bound=Callable[..., Any])
user_repository = UserRepository(lambda: _store, _store_lock)
task_repository = TaskRepository(lambda: _store, _store_lock)


def rate_limit_key() -> str:
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and separator and token:
        try:
            user_id = decode_token(token)
            if user_repository.get_by_id(user_id) is not None:
                return f"user:{user_id}"
        except ValueError:
            pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    application_limits=["100 per minute"],
    headers_enabled=True,
    in_memory_fallback=["100 per minute"],
)


def init_db() -> None:
    """Reset the in-memory store to the current schema."""
    global _store
    with _store_lock:
        _store = {"users": [], "tasks": [], "next_user_id": 1, "next_task_id": 1}


def migrate_db() -> None:
    """Add auth fields without discarding tasks from the legacy schema."""
    global _store
    with _store_lock:
        if not _store:
            _store = {
                "users": [],
                "tasks": [],
                "next_user_id": 1,
                "next_task_id": 1,
            }
            return

        _store.setdefault("users", [])
        _store.setdefault("tasks", [])
        for task in _store["tasks"]:
            task.setdefault("owner_id", None)
        _store.setdefault("next_user_id", 1)
        _store.setdefault("next_task_id", _store.pop("next_id", 1))


def create_user(username: str, password: str) -> User | None:
    return user_repository.create(username, password)


def find_user(username: str) -> User | None:
    return user_repository.get_by_username(username)


def find_user_by_id(user_id: int) -> User | None:
    return user_repository.get_by_id(user_id)


def create_task(title: str, owner_id: int | None = None) -> dict[str, Any]:
    return task_repository.create(title, owner_id)


def get_tasks(owner_id: int | None = None) -> list[dict[str, Any]]:
    return task_repository.get_all(owner_id)


def get_task(task_id: int, owner_id: int | None = None) -> dict[str, Any] | None:
    return task_repository.get_by_id(task_id, owner_id)


def fetch_task(task_id: int, owner_id: int | None = None) -> dict[str, Any] | None:
    return get_task(task_id, owner_id)


def update_task(
    task_id: int,
    title: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
) -> dict[str, Any] | None:
    return task_repository.update(
        task_id, title=title, status=status, owner_id=owner_id
    )


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user: User) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(seconds=app.config["JWT_TTL_SECONDS"])).timestamp()
        ),
    }
    segments = [
        _base64url_encode(json.dumps(value, separators=(",", ":")).encode())
        for value in (header, payload)
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(
        app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
    ).digest()
    return ".".join((*segments, _base64url_encode(signature)))


def decode_token(token: str) -> int:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        supplied_signature = _base64url_decode(encoded_signature)
        expected_signature = hmac.new(
            app.config["JWT_SECRET"].encode(),
            f"{encoded_header}.{encoded_payload}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        if header.get("alg") != "HS256" or not hmac.compare_digest(
            supplied_signature, expected_signature
        ):
            raise ValueError
        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError
        return int(payload["sub"])
    except (
        AttributeError,
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError("invalid token") from error


def auth_required(view: F) -> F:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            user = user_repository.get_by_id(decode_token(token))
        except ValueError:
            user = None
        if user is None:
            return jsonify({"error": "invalid token"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped  # type: ignore[return-value]


def _credentials() -> tuple[str, str] | None:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return None
    return username.strip(), password


@app.post("/auth/register")
def register():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repository.create(*credentials)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user.id, "username": user.username}), 201


@app.post("/auth/login")
def login():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    user = user_repository.get_by_username(username)
    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user)})


@app.get("/tasks")
@auth_required
def list_tasks():
    cursor_value = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        cursor = int(cursor_value) if cursor_value is not None else None
        limit = int(limit_value)
        if cursor is not None and cursor <= 0:
            raise ValueError
        if not 1 <= limit <= 100:
            raise ValueError
        tasks, next_cursor, total = task_repository.paginate(
            g.current_user.id, cursor, limit
        )
    except ValueError:
        return jsonify({"error": "cursor must be a valid task id and limit must be between 1 and 100"}), 400
    return jsonify(
        {
            "data": tasks,
            "next_cursor": str(next_cursor) if next_cursor is not None else None,
            "total": total,
        }
    )


@app.post("/tasks")
@auth_required
def add_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(task_repository.create(title.strip(), g.current_user.id)), 201


@app.get("/tasks/<int:task_id>")
@auth_required
def show_task(task_id: int):
    task = task_repository.get_by_id(task_id, g.current_user.id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@auth_required
def edit_task(task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    existing_task = task_repository.get_by_id(task_id, g.current_user.id)
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404
    task = task_repository.update(
        task_id,
        title=data.get("title"),
        status=data.get("status"),
        owner_id=g.current_user.id,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if existing_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.current_user.username, task["title"])
    return jsonify(task)


migrate_db()


if __name__ == "__main__":
    app.run(debug=True)
