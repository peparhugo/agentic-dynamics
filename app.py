"""A small SQLite-backed task management API with JWT authentication."""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from tasks import send_notification_email
from repositories import TaskRepository, UserRepository, initialize_database

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_LIFETIME = 24 * 60 * 60


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    initialize_database(get_db)


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def make_token(user_id):
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({"sub": user_id, "exp": int(time.time()) + JWT_LIFETIME}, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}".encode()
    signature = _encode(hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def get_current_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        header, payload, signature = authorization[7:].split(".")
        unsigned = f"{header}.{payload}".encode()
        expected = _encode(hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_decode(payload))
        token_header = json.loads(_decode(header))
        if token_header != {"alg": "HS256", "typ": "JWT"}:
            return None
        if claims.get("exp", 0) <= time.time() or not isinstance(claims.get("sub"), int) or isinstance(claims.get("sub"), bool):
            return None
        return UserRepository(get_db).find_by_id(claims["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def create_task(title, owner_id):
    now = datetime.now(timezone.utc).isoformat()
    return TaskRepository(get_db).create_task(title, "pending", now, owner_id)


def get_tasks(owner_id):
    return TaskRepository(get_db).list_for_owner(owner_id)


def get_task(task_id, owner_id):
    return TaskRepository(get_db).find_for_owner(task_id, owner_id)


def update_task(task_id, owner_id, title=None, status=None):
    values = {}
    if title is not None:
        values["title"] = title
    if status is not None:
        values["status"] = status
    return TaskRepository(get_db).update_for_owner(task_id, owner_id, values)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    try:
        user_id = UserRepository(get_db).create(
            {"username": username.strip(), "password_hash": generate_password_hash(password)}
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username.strip()}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    user = UserRepository(get_db).find_by_username(data.get("username")) if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": make_token(user["id"])})


@app.get("/tasks")
@authenticated
def list_tasks():
    return jsonify(get_tasks(g.user["id"]))


@app.post("/tasks")
@authenticated
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title") if isinstance(data, dict) else None
    title = title.strip() if isinstance(title, str) else ""
    if not title:
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title, g.user["id"])), 201


@app.get("/tasks/<int:task_id>")
@authenticated
def show_task(task_id):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@authenticated
def edit_task(task_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    previous_task = get_task(task_id, g.user["id"])
    task = update_task(task_id, g.user["id"], data.get("title", "").strip() if "title" in data else None, data.get("status"))
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.user["username"], task["title"])
    return jsonify(task)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
