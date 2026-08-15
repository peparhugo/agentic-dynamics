"""A small Flask task-management API backed by a JSON flat file."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
from threading import Lock

from functools import wraps

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email
from repositories import TaskRepository, UserRepository, initialize_store


app = Flask(__name__)
app.config["TASKS_FILE"] = os.environ.get("TASKS_FILE", "tasks.json")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_MINUTES"] = 60
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
    "RATELIMIT_STORAGE_URI", "redis://localhost:6379/1"
)
app.config["RATELIMIT_HEADERS_ENABLED"] = True

_storage_lock = Lock()


def _rate_limit_key():
    user = _current_user_from_token()
    return f"user:{user['id']}" if user else get_remote_address()


limiter = Limiter(
    key_func=_rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=app.config["RATELIMIT_STORAGE_URI"],
)


def init_db():
    """Initialize the flat-file schema and migrate pre-auth task records."""
    initialize_store(app.config["TASKS_FILE"])


def _task_repository():
    return TaskRepository(app.config["TASKS_FILE"], _storage_lock)


def _user_repository():
    return UserRepository(app.config["TASKS_FILE"], _storage_lock)


def _not_found():
    return jsonify({"error": "task not found"}), 404


def _encode_part(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_part(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _make_token(user):
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(json.dumps({
        "sub": user["id"],
        "username": user["username"],
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=app.config["JWT_EXPIRATION_MINUTES"])).timestamp()),
    }, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(app.config["JWT_SECRET"].encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode_part(signature)}"


def _current_user_from_token():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    parts = authorization[7:].split(".")
    if len(parts) != 3:
        return None
    header_part, payload_part, signature_part = parts
    message = f"{header_part}.{payload_part}".encode("ascii")
    expected = hmac.new(app.config["JWT_SECRET"].encode(), message, hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(expected, _decode_part(signature_part)):
            return None
        header = json.loads(_decode_part(header_part))
        payload = json.loads(_decode_part(payload_part))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        return None
    if not isinstance(payload.get("exp"), (int, float)) or payload["exp"] < datetime.now(timezone.utc).timestamp():
        return None
    return _user_repository().find_by_id(payload.get("sub"))


def jwt_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = _current_user_from_token()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.current_user = user
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
    user_repository = _user_repository()
    if user_repository.find_by_username(username):
        return jsonify({"error": "username already exists"}), 409
    email = None
    if isinstance(data.get("email"), str) and data["email"].strip():
        email = data["email"].strip()
    user = user_repository.create_user(
        username,
        generate_password_hash(password),
        email,
    )
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    user = _user_repository().find_by_username(username)
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": _make_token(user)})


@app.post("/tasks")
@jwt_required
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    task = _task_repository().create_task(
        title.strip(),
        g.current_user["id"],
        datetime.now(timezone.utc).isoformat(),
    )
    return jsonify(task), 201


@app.get("/tasks")
@jwt_required
def list_tasks():
    cursor_value = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        limit = int(limit_value)
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    if limit < 1 or limit > 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    cursor = None
    if cursor_value is not None:
        try:
            cursor = int(cursor_value)
        except ValueError:
            return jsonify({"error": "cursor must be an integer"}), 400

    tasks, total, has_more = _task_repository().list_page_for_owner(
        g.current_user["id"], cursor, limit
    )
    if tasks is None:
        return jsonify({"error": "invalid cursor"}), 400
    next_cursor = str(tasks[-1]["id"]) if has_more else None
    return jsonify({"data": tasks, "next_cursor": next_cursor, "total": total})


@app.get("/tasks/<int:task_id>")
@jwt_required
def get_task(task_id):
    task = _task_repository().get_for_owner(task_id, g.current_user["id"])
    return jsonify(task) if task else _not_found()


@app.put("/tasks/<int:task_id>")
@jwt_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    task_repository = _task_repository()
    task = task_repository.get_for_owner(task_id, g.current_user["id"])
    if task is None:
        return _not_found()
    was_completed = task.get("status") == "completed"
    changes = {}
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        changes["title"] = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status must be a non-empty string"}), 400
        changes["status"] = data["status"].strip()
    task = task_repository.update_for_owner(task_id, g.current_user["id"], changes)
    became_completed = task["status"] == "completed" and not was_completed
    owner = _user_repository().find_by_id(task.get("owner_id"))
    if became_completed:
        user_email = (owner or {}).get("email") or (owner or {}).get("username")
        try:
            send_notification_email.delay(user_email, task["title"])
        except Exception:
            # A broker outage must not turn a successful task update into an error.
            app.logger.exception("Unable to queue task completion notification")
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run()
