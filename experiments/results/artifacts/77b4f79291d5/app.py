"""Flask API for managing tasks."""

from datetime import datetime, timezone
from functools import wraps
import base64
import binascii
import hashlib
import hmac
import json
import os

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from werkzeug.security import check_password_hash, generate_password_hash

from celery_tasks import send_notification_email
from repositories import DuplicateUserError, TaskRepository, UserRepository


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-development-secret")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def init_db():
    """Create the schema and migrate databases created by older versions."""
    UserRepository.initialize_schema(DATABASE)
    TaskRepository.initialize_schema(DATABASE)


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user):
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(
        json.dumps(
            {"sub": user["id"], "username": user["username"]},
            separators=(",", ":"),
        ).encode()
    )
    unsigned = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode(signature)}"


def decode_token(token):
    header, payload, signature = token.split(".")
    unsigned = f"{header}.{payload}".encode("ascii")
    expected = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
    if not hmac.compare_digest(_decode(signature), expected):
        raise ValueError("invalid signature")
    decoded_header = json.loads(_decode(header))
    decoded_payload = json.loads(_decode(payload))
    if decoded_header.get("alg") != "HS256" or not isinstance(decoded_payload.get("sub"), int):
        raise ValueError("invalid token claims")
    return decoded_payload


def rate_limit_key():
    """Use the authenticated user when possible, otherwise the client IP."""
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        try:
            return f"user:{decode_token(authorization[7:])['sub']}"
        except (
            ValueError,
            KeyError,
            TypeError,
            binascii.Error,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            pass
    return f"ip:{request.remote_addr or 'unknown'}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=REDIS_URL,
    headers_enabled=True,
    in_memory_fallback_enabled=True,
)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        try:
            claims = decode_token(authorization[7:])
            user = UserRepository(DATABASE).get(claims["sub"])
            if user is None:
                raise ValueError("unknown user")
        except (
            ValueError,
            KeyError,
            TypeError,
            binascii.Error,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return jsonify({"error": "invalid token"}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400

    try:
        user = UserRepository(DATABASE).create(
            {"username": username.strip(), "password_hash": generate_password_hash(password)}
        )
    except DuplicateUserError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    user = UserRepository(DATABASE).find_by_username(username)
    if user is None or not isinstance(password, str) or not check_password_hash(
        user["password_hash"], password
    ):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user)})


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    row = TaskRepository(DATABASE).create(
        {"title": title, "created_at": created_at, "owner_id": g.user["id"]}
    )
    return jsonify(task_json(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    raw_limit = request.args.get("limit", "20")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer between 1 and 100"}), 400
    if not 1 <= limit <= 100:
        return jsonify({"error": "limit must be an integer between 1 and 100"}), 400

    raw_cursor = request.args.get("cursor")
    cursor = None
    if raw_cursor is not None:
        try:
            cursor = int(raw_cursor)
        except (TypeError, ValueError):
            return jsonify({"error": "cursor must be an integer"}), 400
        if cursor < 1:
            return jsonify({"error": "cursor must be an integer"}), 400

    repository = TaskRepository(DATABASE)
    rows = repository.list_for_owner(g.user["id"], cursor=cursor, limit=limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = str(rows[-1]["id"]) if has_more else None
    return jsonify(
        {
            "data": [task_json(row) for row in rows],
            "next_cursor": next_cursor,
            "total": repository.count_for_owner(g.user["id"]),
        }
    )


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    row = TaskRepository(DATABASE).get_for_owner(task_id, g.user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_json(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    updates = {}
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        updates["title"] = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status must be a non-empty string"}), 400
        updates["status"] = data["status"].strip()
    if not updates:
        return jsonify({"error": "title or status is required"}), 400

    repository = TaskRepository(DATABASE)
    row = repository.get_for_owner(task_id, g.user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    updated = repository.update_for_owner(task_id, g.user["id"], updates)
    if row["status"] != "completed" and updated["status"] == "completed":
        send_notification_email.delay(g.user["username"], updated["title"])
    return jsonify(task_json(updated))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
