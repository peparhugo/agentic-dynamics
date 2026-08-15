"""Flat-file Flask API for managing authenticated users' tasks."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
from threading import Lock
from typing import Any

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)
app.config["TASKS_FILE"] = os.environ.get("TASKS_FILE", "tasks.json")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_HOURS"] = 24
_storage_lock = Lock()


def _storage_path() -> Path:
    return Path(app.config["TASKS_FILE"])


def _empty_data() -> dict[str, list[dict]]:
    return {"users": [], "tasks": []}


def init_storage() -> None:
    """Create storage or migrate the legacy task-list format in place."""
    path = _storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_data(_empty_data())
        return

    try:
        with path.open(encoding="utf-8") as data_file:
            stored_data = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        _write_data(_empty_data())
        return

    if isinstance(stored_data, list):
        # Legacy tasks had no authenticated owner; preserve them but expose none.
        for task in stored_data:
            if isinstance(task, dict):
                task.setdefault("owner_id", None)
        _write_data({"users": [], "tasks": stored_data})


def _read_data() -> dict[str, list[dict]]:
    path = _storage_path()
    if not path.exists():
        init_storage()
    try:
        with path.open(encoding="utf-8") as data_file:
            data = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        return _empty_data()
    if isinstance(data, list):
        return {"users": [], "tasks": data}
    if not isinstance(data, dict):
        return _empty_data()
    users = data.get("users")
    tasks = data.get("tasks")
    return {
        "users": users if isinstance(users, list) else [],
        "tasks": tasks if isinstance(tasks, list) else [],
    }


def _write_data(data: dict[str, list[dict]]) -> None:
    path = _storage_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(data, temporary_file, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        os.unlink(temporary_name)
        raise


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _create_token(user_id: int) -> str:
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _base64url_encode(json.dumps({"sub": user_id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"])).timestamp())}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}"
    signature = hmac.new(app.config["JWT_SECRET"].encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _authenticated_user_id() -> int | None:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        header, payload, signature = authorization[7:].split(".")
        signing_input = f"{header}.{payload}"
        expected_signature = hmac.new(app.config["JWT_SECRET"].encode(), signing_input.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_base64url_decode(signature), expected_signature):
            return None
        decoded_header = json.loads(_base64url_decode(header))
        decoded_payload = json.loads(_base64url_decode(payload))
        if decoded_header != {"alg": "HS256", "typ": "JWT"} or not isinstance(decoded_payload["sub"], int):
            return None
        if not isinstance(decoded_payload["exp"], int) or decoded_payload["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return decoded_payload["sub"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _require_user() -> tuple[int | None, Any | None]:
    user_id = _authenticated_user_id()
    if user_id is None:
        return None, (jsonify(error="authentication required"), 401)
    return user_id, None


def _repositories() -> tuple[TaskRepository, UserRepository]:
    return (
        TaskRepository(_read_data, _write_data, _storage_lock),
        UserRepository(_read_data, _write_data, _storage_lock),
    )


@app.post("/auth/register")
def register():
    data = _json_body()
    username = data.get("username") if data else None
    password = data.get("password") if data else None
    email = data.get("email") if data else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify(error="username and password are required"), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify(error="email must be a non-empty string"), 400

    _, users = _repositories()
    user_attributes = {"username": username.strip(), "password_hash": generate_password_hash(password)}
    if email is not None:
        user_attributes["email"] = email.strip()
    user = users.create_if_username_available(user_attributes)
    if user is None:
        return jsonify(error="username already exists"), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.post("/auth/login")
def login():
    data = _json_body()
    username = data.get("username") if data else None
    password = data.get("password") if data else None
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="username and password are required"), 400
    _, users = _repositories()
    user = users.get_by_username(username)
    if user is None or not check_password_hash(user.get("password_hash", ""), password):
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=_create_token(user["id"]))


@app.post("/tasks")
def create_task():
    user_id, error = _require_user()
    if error:
        return error
    data = _json_body()
    title = data.get("title") if data else None
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400

    tasks, _ = _repositories()
    task = tasks.create(
        {"title": title.strip(), "status": "pending", "created_at": datetime.now(timezone.utc).isoformat(), "owner_id": user_id}
    )
    return jsonify(task), 201


@app.get("/tasks")
def list_tasks():
    user_id, error = _require_user()
    if error:
        return error
    tasks, _ = _repositories()
    tasks = tasks.list_for_owner(user_id)
    return jsonify(sorted(tasks, key=lambda task: task["created_at"], reverse=True))


@app.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    user_id, error = _require_user()
    if error:
        return error
    tasks, _ = _repositories()
    task = tasks.get_for_owner(task_id, user_id)
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
def update_task(task_id: int):
    user_id, error = _require_user()
    if error:
        return error
    data = _json_body()
    if data is None or not any(field in data for field in ("title", "status")):
        return jsonify(error="title or status is required"), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify(error="title must be a non-empty string"), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify(error="status must be a string"), 400

    tasks, users = _repositories()
    changes = {}
    if "title" in data:
        changes["title"] = data["title"].strip()
    if "status" in data:
        changes["status"] = data["status"]
    result = tasks.update_for_owner(task_id, user_id, changes)
    if result is None:
        return jsonify(error="task not found"), 404
    task, was_completed = result
    should_notify = not was_completed and task.get("status") == "completed"
    user = users.get_by_id(user_id)
    user_email = user.get("email", user.get("username")) if user else None
    if should_notify and user_email:
        send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
