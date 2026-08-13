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
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER REFERENCES users(id)
            )
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            # Existing tasks remain valid, but have no owner and are not exposed.
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")


def create_task(title: str, owner_id: int) -> dict:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
            (title, created_at, owner_id),
        )
        task_id = cursor.lastrowid
    return get_task(task_id, owner_id)


def get_tasks(owner_id: int) -> list[dict]:
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
    return dict(row) if row else None


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    if get_task(task_id, owner_id) is None:
        return None

    updates = []
    values = []
    if title is not None:
        updates.append("title = ?")
        values.append(title)
    if status is not None:
        updates.append("status = ?")
        values.append(status)

    if updates:
        values.append(task_id)
        with get_db() as connection:
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                values + [owner_id],
            )
    return get_task(task_id, owner_id)


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
    if not username or not data["password"]:
        return error("username and password are required", 400)
    try:
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(data["password"])),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return error("username already exists", 409)
    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        return error("username and password are required", 400)
    with get_db() as connection:
        user = connection.execute("SELECT id, password_hash FROM users WHERE username = ?", (data["username"].strip(),)).fetchone()
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

    task = update_task(task_id, user_id, title.strip() if title is not None else None, status)
    if task is None:
        return error("task not found", 404)
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
