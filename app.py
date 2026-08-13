"""Flask API for managing tasks stored in SQLite."""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24


def get_db() -> sqlite3.Connection:
    """Return a connection that exposes SQLite rows as dictionaries."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create tables and migrate existing task databases."""
    users = UserRepository(get_db)
    users.initialize()
    TaskRepository(get_db).initialize()


def create_task(title: str, owner_id: int) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    return TaskRepository(get_db).create_task(title, created_at, owner_id)


def get_tasks(owner_id: int) -> list[dict]:
    return TaskRepository(get_db).list_for_owner(owner_id)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return TaskRepository(get_db).get_for_owner(task_id, owner_id)


def get_user_email(user_id: int) -> str | None:
    """Return the owner's email, falling back to their existing username."""
    return UserRepository(get_db).get_email(user_id)


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    values = {}
    if title is not None:
        values["title"] = title
    if status is not None:
        values["status"] = status
    return TaskRepository(get_db).update_for_owner(task_id, owner_id, values)


def error(message: str, status: int):
    return jsonify({"error": message}), status


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _base64url_encode(json.dumps({"sub": user_id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp())}, separators=(",", ":")).encode())
    signature = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{_base64url_encode(signature)}"


def get_token_user_id(token: str) -> int | None:
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _base64url_decode(signature)):
            return None
        claims = json.loads(_base64url_decode(payload))
        if not isinstance(claims.get("sub"), int) or claims["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return claims["sub"]
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = get_token_user_id(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return error("authentication required", 401)
        return view(user_id, *args, **kwargs)
    return wrapped


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        return error("username and password are required", 400)
    username = data["username"].strip()
    email = data.get("email")
    if not username or not data["password"]:
        return error("username and password are required", 400)
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return error("email must be a non-empty string", 400)
    try:
        user_id = UserRepository(get_db).create_user(
            username, generate_password_hash(data["password"]), email.strip() if email else None
        )
    except sqlite3.IntegrityError:
        return error("username already exists", 409)
    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        return error("username and password are required", 400)
    user = UserRepository(get_db).get_by_username(data["username"].strip())
    if user is None or not check_password_hash(user["password_hash"], data["password"]):
        return error("invalid username or password", 401)
    return jsonify({"token": create_token(user["id"])})


@app.post("/tasks")
@require_auth
def add_task(user_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("title"), str):
        return error("title is required", 400)

    title = data["title"].strip()
    if not title:
        return error("title is required", 400)
    return jsonify(create_task(title, user_id)), 201


@app.get("/tasks")
@require_auth
def list_tasks(user_id: int):
    return jsonify(get_tasks(user_id))


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(user_id: int, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return error("task not found", 404)
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def edit_task(user_id: int, task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("JSON body is required", 400)

    title = data.get("title")
    status = data.get("status")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        return error("title must be a non-empty string", 400)
    if status is not None and not isinstance(status, str):
        return error("status must be a string", 400)
    if title is None and status is None:
        return error("title or status is required", 400)

    previous_task = get_task(task_id, user_id)
    if previous_task is None:
        return error("task not found", 404)

    task = update_task(task_id, user_id, title.strip() if title is not None else None, status)
    if task is None:
        return error("task not found", 404)
    if status == "completed" and previous_task["status"] != "completed":
        user_email = get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
