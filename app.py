import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from notification_tasks import send_notification_email
from repositories import (
    DuplicateRecordError,
    TaskRepository,
    UserRepository,
    open_database,
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_SECONDS"] = 3600
app.config["RATELIMIT_STORAGE_URI"] = os.environ.get(
    "RATELIMIT_STORAGE_URI", "redis://localhost:6379/0"
)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def rate_limit_key():
    authorization = request.headers.get("Authorization", "")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and separator and token:
        user_id = decode_token(token)
        if user_id is not None:
            return f"user:{user_id}"
    return f"address:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=app.config["RATELIMIT_STORAGE_URI"],
    headers_enabled=True,
)


def get_db():
    return open_database(DATABASE)


def init_db():
    UserRepository(get_db).initialize_schema()
    TaskRepository(get_db).initialize_schema()


def _base64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    now = datetime.now(timezone.utc)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"])).timestamp()
        ),
    }
    segments = [
        _base64url_encode(json.dumps(part, separators=(",", ":")).encode())
        for part in (header, payload)
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(
        app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
    ).digest()
    return ".".join((*segments, _base64url_encode(signature)))


def decode_token(token):
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        expected_signature = hmac.new(
            app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
        ).digest()
        signature = _base64url_decode(signature_part)
        header = json.loads(_base64url_decode(header_part))
        payload = json.loads(_base64url_decode(payload_part))
        if header.get("alg") != "HS256" or not hmac.compare_digest(
            signature, expected_signature
        ):
            return None
        if not isinstance(payload.get("exp"), (int, float)) or payload["exp"] <= int(
            datetime.now(timezone.utc).timestamp()
        ):
            return None
        user_id = int(payload["sub"])
        return user_id if user_id > 0 else None
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            return jsonify({"error": "authentication required"}), 401

        user_id = decode_token(token)
        if user_id is None:
            return jsonify({"error": "invalid token"}), 401
        if not UserRepository(get_db).exists(user_id):
            return jsonify({"error": "invalid token"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def credentials_from_request():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return None
    if not isinstance(password, str) or not password:
        return None
    return username.strip(), password


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.post("/auth/register")
def register():
    credentials = credentials_from_request()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    data = request.get_json()
    email = data.get("email", username)
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "email must be a non-empty string"}), 400
    email = email.strip()
    try:
        user_id = UserRepository(get_db).create(
            {
                "username": username,
                "password_hash": generate_password_hash(password),
                "email": email,
            }
        )
    except DuplicateRecordError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    credentials = credentials_from_request()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    user = UserRepository(get_db).get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.post("/tasks")
@require_auth
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    repository = TaskRepository(get_db)
    task_id = repository.create(
        {"title": title, "created_at": created_at, "owner_id": g.user_id}
    )
    row = repository.get_for_owner(task_id, g.user_id)

    return jsonify(task_to_dict(row)), 201


@app.get("/tasks")
@require_auth
def list_tasks():
    cursor = request.args.get("cursor")
    limit = request.args.get("limit", "20")
    try:
        cursor = int(cursor) if cursor is not None else None
        limit = int(limit)
    except ValueError:
        return jsonify({"error": "cursor and limit must be integers"}), 400
    if cursor is not None and cursor <= 0:
        return jsonify({"error": "cursor must be a positive integer"}), 400
    if limit <= 0 or limit > 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    rows, total, has_more = TaskRepository(get_db).list_for_owner(
        g.user_id, cursor=cursor, limit=limit
    )
    return jsonify(
        {
            "data": [task_to_dict(row) for row in rows],
            "next_cursor": str(rows[-1]["id"]) if has_more else None,
            "total": total,
        }
    )


@app.get("/tasks/<int:task_id>")
@require_auth
def get_task(task_id):
    row = TaskRepository(get_db).get_for_owner(task_id, g.user_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_to_dict(row))


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object is required"}), 400

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

    existing, row = TaskRepository(get_db).update_for_owner(
        task_id, g.user_id, updates
    )
    if existing is None:
        return jsonify({"error": "task not found"}), 404

    if existing["status"] != "completed" and row["status"] == "completed":
        send_notification_email.delay(existing["email"], row["title"])

    return jsonify(task_to_dict(row))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
