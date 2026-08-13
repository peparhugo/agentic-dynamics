"""SQLite-backed task management API."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from repositories import BaseRepository, TaskRepository, UserRepository
from tasks import send_notification_email


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-only-secret")
JWT_EXPIRATION_HOURS = 24


def get_db() -> sqlite3.Connection:
    """Return a connection that exposes rows by column name."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create and migrate the database schema without discarding existing tasks."""
    BaseRepository.initialize_schema(get_db)


def encode_token(user_id: int) -> str:
    """Create a signed, expiring JWT for a user."""
    def encode_part(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    header = encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = encode_part(
        json.dumps(
            {
                "sub": user_id,
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{encode_part(signature)}"


def decode_token(token: str) -> int | None:
    """Validate a JWT and return its subject, or None when it is invalid."""
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if not isinstance(claims.get("sub"), int) or claims.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return claims["sub"]
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def authentication_required(view):
    """Require a valid bearer token and expose its user id to the view."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = decode_token(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        if not UserRepository(get_db).exists(user_id):
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def task_not_found():
    return jsonify({"error": "task not found"}), 404


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400
    user_id = UserRepository(get_db).create_user(
        username.strip(), email.strip() if email else username.strip(), generate_password_hash(password)
    )
    if user_id is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username.strip()}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401
    user = UserRepository(get_db).find_by_username(username.strip())
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": encode_token(user["id"])})


@app.post("/tasks")
@authentication_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    task = {
        "title": title.strip(),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "owner_id": g.user_id,
    }
    task["id"] = TaskRepository(get_db).create(**task)
    del task["owner_id"]
    return jsonify(task), 201


@app.get("/tasks")
@authentication_required
def list_tasks():
    rows = TaskRepository(get_db).list_for_owner(g.user_id)
    # SQLite retrieval is intentionally unsorted; sort the loaded task rows here.
    tasks = [dict(row) for row in rows]
    tasks.sort(key=lambda task: task["created_at"], reverse=True)
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
@authentication_required
def get_task(task_id: int):
    row = TaskRepository(get_db).find_for_owner(task_id, g.user_id)
    if row is None:
        return task_not_found()
    return jsonify(dict(row))


@app.put("/tasks/<int:task_id>")
@authentication_required
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    updates = {}

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        updates["title"] = title.strip()
    if "status" in data:
        status = data["status"]
        if not isinstance(status, str):
            return jsonify({"error": "status must be a string"}), 400
        updates["status"] = status

    repository = TaskRepository(get_db)
    row = repository.find_for_owner_with_email(task_id, g.user_id)
    if row is None:
        return task_not_found()
    repository.update_for_owner(task_id, g.user_id, **updates)
    task = repository.find_for_owner(task_id, g.user_id)
    if data.get("status") == "completed" and row["status"] != "completed":
        send_notification_email.delay(row["email"], task["title"])
    return jsonify(dict(task))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
