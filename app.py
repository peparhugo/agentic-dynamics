"""Minimal Flask Todo API."""

from flask import Flask, request, jsonify, g
from datetime import datetime
from functools import wraps
import base64
import binascii
import hashlib
import hmac
import json
import os
from sqlite3 import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from tasks import send_notification_email
from repositories import TaskRepository, UserRepository, get_connection, initialize_database

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_LIFETIME_SECONDS = 3600
VALID_STATUSES = {"pending", "done", "completed"}


def get_db():
    return get_connection(DATABASE)


def init_db():
    initialize_database(DATABASE)


def create_user(username: str, password: str) -> dict:
    return UserRepository(DATABASE).create({
        "username": username,
        "password_hash": generate_password_hash(password),
    })


def find_user(username: str):
    return UserRepository(DATABASE).find_by_username(username)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    now = int(datetime.utcnow().timestamp())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({"sub": str(user_id), "iat": now, "exp": now + JWT_LIFETIME_SECONDS}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(app.config["JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def decode_token(token: str) -> int:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected = hmac.new(app.config["JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64decode(parts[2])):
        raise ValueError("invalid token")
    header = json.loads(_b64decode(parts[0]))
    payload = json.loads(_b64decode(parts[1]))
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise ValueError("invalid token")
    if not isinstance(payload.get("sub"), str) or int(payload["exp"]) <= int(datetime.utcnow().timestamp()):
        raise ValueError("expired token")
    return int(payload["sub"])


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        try:
            user_id = decode_token(authorization[7:].strip())
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
            return jsonify({"error": "invalid or expired token"}), 401
        user = UserRepository(DATABASE).find_public_by_id(user_id)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user = user
        return view(*args, **kwargs)
    return wrapped


def create_task(title: str, owner_id: int) -> dict:
    return TaskRepository(DATABASE).create_for_owner(title, owner_id)


def get_tasks(owner_id: int):
    return TaskRepository(DATABASE).list_for_owner(owner_id)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return TaskRepository(DATABASE).get_for_owner(task_id, owner_id)


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    values = {}
    if title is not None:
        values["title"] = title
    if status is not None:
        values["status"] = status
    return TaskRepository(DATABASE).update_for_owner(task_id, owner_id, values)


init_db()


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    if find_user(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    try:
        user = create_user(username, password)
    except IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    user = find_user(username) if isinstance(username, str) and isinstance(password, str) else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"]), "user": {"id": user["id"], "username": user["username"]}})


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.user["id"]))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title.strip(), g.user["id"])), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    existing_task = get_task(task_id, g.user["id"])
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404
    if "status" in data and data["status"] not in VALID_STATUSES:
        return jsonify({"error": "invalid status"}), 422
    if "title" in data and not isinstance(data["title"], str):
        return jsonify({"error": "title must be a string"}), 400
    task = update_task(task_id, g.user["id"], title=data.get("title"), status=data.get("status"))
    if existing_task["status"] != "completed" and data.get("status") == "completed":
        send_notification_email.delay(g.user["username"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
