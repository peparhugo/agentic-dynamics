"""Flask task-management API backed by a JSON flat file."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import os

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)

# Kept configurable so deployments and tests can use an isolated data file.
DATABASE = os.environ.get("DATABASE", "tasks.json")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24
RATE_LIMIT_STORAGE_URI = os.environ.get("RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/0")


task_repository = TaskRepository(lambda: DATABASE)
user_repository = UserRepository(lambda: DATABASE)


def init_db() -> None:
    """Create and migrate the flat-file schema without discarding stored tasks."""
    task_repository.initialize()


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _encode_token(user_id: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    }
    encoded_header = _base64url(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _base64url(json.dumps(payload, separators=(",", ":")).encode())
    signed_data = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(JWT_SECRET.encode(), signed_data.encode(), hashlib.sha256).digest()
    return f"{signed_data}.{_base64url(signature)}"


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode_token(token: str) -> int | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signed_data = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            JWT_SECRET.encode(), signed_data.encode(), hashlib.sha256
        ).digest()
        supplied_signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected_signature, supplied_signature):
            return None
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, int) or payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return user_id
    except (AttributeError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _rate_limit_key() -> str:
    """Use the token subject for authenticated requests and an IP otherwise."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    user_id = _decode_token(token) if scheme == "Bearer" and token else None
    return f"user:{user_id}" if user_id is not None else request.remote_addr or "anonymous"


limiter = Limiter(
    _rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    headers_enabled=True,
    storage_uri=RATE_LIMIT_STORAGE_URI,
)


@app.errorhandler(429)
def rate_limit_exceeded(error):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    response.headers["Retry-After"] = str(getattr(error, "retry_after", 60) or 60)
    return response


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = _decode_token(token) if scheme == "Bearer" and token else None
        if user_id is None or user_repository.get_by_id(user_id) is None:
            return jsonify({"error": "unauthorized"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


@app.route("/auth/register", methods=["POST"])
def register():
    data = _json_body()
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400
    username = username.strip()
    if user_repository.get_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user_data = {
        "username": username,
        "password_hash": generate_password_hash(password),
    }
    if email is not None:
        user_data["email"] = email.strip()
    user = user_repository.create(user_data)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = _json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401
    user = user_repository.get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": _encode_token(user["id"])})


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user_id: int):
    cursor = request.args.get("cursor")
    limit_value = request.args.get("limit", "20")
    try:
        limit = int(limit_value)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    if not 1 <= limit <= 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    tasks = task_repository.list_for_owner(user_id)
    start = 0
    if cursor is not None:
        try:
            cursor_id = int(cursor)
        except ValueError:
            return jsonify({"error": "cursor must be an integer"}), 400
        start = next((index + 1 for index, task in enumerate(tasks) if task["id"] == cursor_id), None)
        if start is None:
            return jsonify({"error": "cursor not found"}), 400

    page = tasks[start : start + limit]
    next_cursor = str(page[-1]["id"]) if start + limit < len(tasks) else None
    return jsonify({"data": page, "next_cursor": next_cursor, "total": len(tasks)})


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task(user_id: int):
    data = _json_body()
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    task = task_repository.create(
        {
            "title": title.strip(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": user_id,
        }
    )
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(user_id: int, task_id: int):
    task = task_repository.get_for_owner(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(user_id: int, task_id: int):
    data = _json_body()
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400

    title = data.get("title")
    status = data.get("status")
    if "title" in data and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400

    previous_task = task_repository.get_for_owner(task_id, user_id)
    changes = {}
    if title is not None:
        changes["title"] = title.strip()
    if status is not None:
        changes["status"] = status
    task = task_repository.update_for_owner(task_id, user_id, changes)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task is not None and previous_task["status"] != "completed" and task["status"] == "completed":
        owner = user_repository.get_by_id(user_id)
        if owner is not None and owner.get("email"):
            send_notification_email.delay(owner["email"], task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
