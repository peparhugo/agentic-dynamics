"""A small SQLite-backed task management API with JWT authentication."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from notifications import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
TOKEN_LIFETIME = timedelta(hours=24)


def init_db():
    """Create the schema and migrate databases created by older versions."""
    UserRepository(DATABASE).create_table()
    TaskRepository(DATABASE).create_table()


def _encode_part(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_part(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(json.dumps({
        "sub": str(user_id),
        "exp": int((datetime.now(timezone.utc) + TOKEN_LIFETIME).timestamp()),
    }, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}"
    signature = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{_encode_part(signature)}"


def decode_token(token: str) -> int | None:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_decode_part(signature), expected):
            return None
        header_data = json.loads(_decode_part(header))
        data = json.loads(_decode_part(payload))
        if header_data.get("alg") != "HS256" or int(data["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            return None
        user_id = int(data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, Exception):
        return None
    return user_id


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        user_id = decode_token(authorization[7:].strip())
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401
        user = UserRepository(DATABASE).find_by_id(user_id)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.current_user = dict(user)
        return view(*args, **kwargs)

    return wrapped


def create_task(title: str, owner_id: int | None = None) -> dict:
    return TaskRepository(DATABASE).create_task(title, datetime.utcnow().isoformat(), owner_id)


def get_tasks(owner_id: int | None = None):
    return TaskRepository(DATABASE).list_tasks(owner_id)


def get_task(task_id: int, owner_id: int | None = None) -> dict | None:
    return TaskRepository(DATABASE).get_task(task_id, owner_id)


def fetch_task(task_id: int) -> dict | None:
    """Compatibility alias for callers using the original helper name."""
    return get_task(task_id)


def update_task(task_id: int, title: str | None = None, status: str | None = None, owner_id: int | None = None) -> dict | None:
    return TaskRepository(DATABASE).update_task(task_id, title, status, owner_id)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "username and password are required"}), 400
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        user_id = UserRepository(DATABASE).create({
            "username": username,
            "password_hash": generate_password_hash(password),
        })
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "invalid credentials"}), 401
    user = UserRepository(DATABASE).find_by_username(data.get("username"))
    if user is None or not isinstance(data.get("password"), str) or not check_password_hash(user["password_hash"], data["password"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.route("/tasks", methods=["GET"])
@authenticated
def list_tasks():
    return jsonify(get_tasks(g.current_user["id"]))


@app.route("/tasks", methods=["POST"])
@authenticated
def add_task():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title.strip(), g.current_user["id"])), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@authenticated
def show_task(task_id: int):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@authenticated
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    previous_task = get_task(task_id, g.current_user["id"])
    task = update_task(task_id, data.get("title"), data.get("status"), g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.current_user["username"], task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
