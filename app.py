"""Flask API for managing per-user tasks in memory."""

from __future__ import annotations

import base64
import binascii
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import hmac
import json
import os
from threading import Lock
from typing import Any, Callable, TypeVar

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email


app = Flask(__name__)
app.config.update(
    JWT_SECRET=os.environ.get("JWT_SECRET", "development-only-secret"),
    JWT_TTL_SECONDS=3600,
)


@dataclass
class User:
    id: int
    username: str
    password_hash: str


@dataclass
class Task:
    id: int
    title: str
    status: str
    created_at: str
    owner_id: int | None


_store: dict[str, Any] = {}
_store_lock = Lock()
F = TypeVar("F", bound=Callable[..., Any])


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
    with _store_lock:
        if any(user["username"] == username for user in _store["users"]):
            return None
        user = User(
            id=_store["next_user_id"],
            username=username,
            password_hash=generate_password_hash(password),
        )
        _store["next_user_id"] += 1
        _store["users"].append(asdict(user))
        return user


def find_user(username: str) -> User | None:
    with _store_lock:
        for user in _store["users"]:
            if user["username"] == username:
                return User(**user)
    return None


def find_user_by_id(user_id: int) -> User | None:
    with _store_lock:
        for user in _store["users"]:
            if user["id"] == user_id:
                return User(**user)
    return None


def create_task(title: str, owner_id: int | None = None) -> dict[str, Any]:
    with _store_lock:
        task = Task(
            id=_store["next_task_id"],
            title=title,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
            owner_id=owner_id,
        )
        _store["next_task_id"] += 1
        stored_task = asdict(task)
        _store["tasks"].append(stored_task)
        return stored_task.copy()


def get_tasks(owner_id: int | None = None) -> list[dict[str, Any]]:
    with _store_lock:
        tasks = [
            task for task in _store["tasks"] if owner_id is None or task["owner_id"] == owner_id
        ]
        tasks.sort(
            key=lambda task: (task["created_at"], task["id"]), reverse=True
        )
        return [task.copy() for task in tasks]


def get_task(task_id: int, owner_id: int | None = None) -> dict[str, Any] | None:
    with _store_lock:
        for task in _store["tasks"]:
            if task["id"] == task_id and (
                owner_id is None or task["owner_id"] == owner_id
            ):
                return task.copy()
    return None


def fetch_task(task_id: int, owner_id: int | None = None) -> dict[str, Any] | None:
    return get_task(task_id, owner_id)


def update_task(
    task_id: int,
    title: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
) -> dict[str, Any] | None:
    with _store_lock:
        for task in _store["tasks"]:
            if task["id"] != task_id or (
                owner_id is not None and task["owner_id"] != owner_id
            ):
                continue
            if title is not None:
                task["title"] = title
            if status is not None:
                task["status"] = status
            return task.copy()
    return None


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
            user = find_user_by_id(decode_token(token))
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
    user = create_user(*credentials)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user.id, "username": user.username}), 201


@app.post("/auth/login")
def login():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    user = find_user(username)
    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user)})


@app.get("/tasks")
@auth_required
def list_tasks():
    return jsonify(get_tasks(g.current_user.id))


@app.post("/tasks")
@auth_required
def add_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title.strip(), g.current_user.id)), 201


@app.get("/tasks/<int:task_id>")
@auth_required
def show_task(task_id: int):
    task = get_task(task_id, g.current_user.id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@auth_required
def edit_task(task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    existing_task = get_task(task_id, g.current_user.id)
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404
    task = update_task(
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
