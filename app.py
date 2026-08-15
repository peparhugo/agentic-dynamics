"""Flask task-management API."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository, initialize_store


app = Flask(__name__)
app.config.update(
    JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-secret-change-me"),
    JWT_EXPIRATION_SECONDS=3600,
)

# Kept as a module setting so deployments and tests can select their data file.
DATABASE = os.environ.get("TASKS_FILE", "tasks.json")


def init_db() -> None:
    """Initialize and migrate the configured data store."""
    initialize_store(DATABASE)


def _user_repository() -> UserRepository:
    return UserRepository(DATABASE)


def _task_repository() -> TaskRepository:
    return TaskRepository(DATABASE, lambda: datetime.now(timezone.utc).isoformat())


def create_user(username: str, password: str) -> dict | None:
    return _user_repository().create(username=username, password=password)


def get_user_by_username(username: str) -> dict | None:
    return _user_repository().get_by_username(username)


def get_user(user_id: int) -> dict | None:
    return _user_repository().get(user_id)


def create_task(title: str, owner_id: int) -> dict:
    return _task_repository().create(title=title, owner_id=owner_id)


def get_tasks(owner_id: int) -> list[dict]:
    return _task_repository().list_for_owner(owner_id)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return _task_repository().get_for_owner(task_id, owner_id)


def update_task(
    task_id: int, owner_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    return _task_repository().update_for_owner(
        task_id, owner_id, title=title, status=status
    )


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"])).timestamp()),
    }
    encoded_header = _base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def decode_token(token: str) -> int | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        supplied_signature = _base64url_decode(encoded_signature)
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None

    if header != {"alg": "HS256", "typ": "JWT"}:
        return None
    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), signing_input.encode(), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return None

    user_id = payload.get("sub")
    expires_at = payload.get("exp")
    if (
        not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or not isinstance(expires_at, int)
        or expires_at <= int(time.time())
    ):
        return None
    return user_id


def jwt_required(view):
    @wraps(view)
    def authenticated_view(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401
        user_id = decode_token(token)
        user = _user_repository().get(user_id) if user_id is not None else None
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return authenticated_view


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
    username, password = credentials
    user = _user_repository().create(username=username, password=password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.post("/auth/login")
def login():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    user = _user_repository().get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.get("/tasks")
@jwt_required
def list_tasks():
    return jsonify(_task_repository().list_for_owner(g.current_user["id"]))


@app.post("/tasks")
@jwt_required
def add_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not data["title"].strip():
        return jsonify({"error": "title is required"}), 400
    task = _task_repository().create(
        title=data["title"].strip(), owner_id=g.current_user["id"]
    )
    return jsonify(task), 201


@app.get("/tasks/<int:task_id>")
@jwt_required
def show_task(task_id: int):
    task = _task_repository().get_for_owner(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@jwt_required
def edit_task(task_id: int):
    repository = _task_repository()
    existing_task = repository.get_for_owner(task_id, g.current_user["id"])
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object is required"}), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    title = data["title"].strip() if "title" in data else None
    task = repository.update_for_owner(
        task_id, g.current_user["id"], title=title, status=data.get("status")
    )
    if existing_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.current_user["username"], task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
