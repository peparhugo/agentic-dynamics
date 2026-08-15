"""A small Flask API for managing tasks.

Tasks are persisted in a JSON file.
"""

from datetime import datetime, timedelta, timezone
import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
from threading import Lock

from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)
DATA_FILE = Path(os.environ.get("TASKS_FILE", "tasks.json"))
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "development-secret-change-me")
JWT_LIFETIME = timedelta(hours=1)
_file_lock = Lock()


def _repositories():
    return UserRepository(DATA_FILE, _file_lock), TaskRepository(DATA_FILE, _file_lock)


def init_storage():
    UserRepository(DATA_FILE, _file_lock).initialize()


def _task_response(task):
    return jsonify(task)


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _create_token(user):
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({
        "sub": str(user["id"]),
        "username": user["username"],
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + JWT_LIFETIME).timestamp()),
    }, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(app.config["JWT_SECRET_KEY"].encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode(signature)}"


def _current_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        header, payload, signature = authorization[7:].split(".")
        expected = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), f"{header}.{payload}".encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_decode(signature), expected):
            return None
        token_header = json.loads(_decode(header))
        claims = json.loads(_decode(payload))
        if token_header.get("alg") != "HS256" or token_header.get("typ") != "JWT":
            return None
        if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        user_id = int(claims["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error, OverflowError):
        return None
    user_repository, _ = _repositories()
    return user_repository.get(user_id)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = _current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    email = data.get("email") if isinstance(data.get("email"), str) else username
    user_repository, _ = _repositories()
    if user_repository.find_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = user_repository.create({
        "username": username,
        "email": email,
        "password_hash": generate_password_hash(password),
    })
    return jsonify({"id": user["id"], "username": user["username"], "email": user["email"]}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    user_repository, _ = _repositories()
    user = user_repository.find_by_username(username)
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": _create_token(user)})


@app.post("/tasks")
@require_auth
def create_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not data["title"].strip():
        return jsonify({"error": "title is required"}), 400

    _, task_repository = _repositories()
    task = task_repository.create_for_user(data["title"].strip(), g.user["id"])
    return _task_response(task), 201


@app.get("/tasks")
@require_auth
def list_tasks():
    _, task_repository = _repositories()
    tasks = task_repository.list_for_user(g.user["id"])
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
@require_auth
def get_task(task_id):
    _, task_repository = _repositories()
    task = task_repository.get_for_user(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return _task_response(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    if not ("title" in data or "status" in data):
        return jsonify({"error": "title or status is required"}), 400

    _, task_repository = _repositories()
    values = {}
    if "title" in data:
        values["title"] = data["title"].strip()
    if "status" in data:
        values["status"] = data["status"]
    result = task_repository.update_for_user(task_id, g.user["id"], values)
    if result is None:
        return jsonify({"error": "task not found"}), 404
    task, previous_status = result
    if data.get("status") == "completed" and previous_status != "completed":
        send_notification_email.delay(g.user.get("email", g.user["username"]), task["title"])
    return _task_response(task)


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "method not allowed"}), 405


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
