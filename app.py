"""Flask task API with JWT authentication and SQLite persistence."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone
from functools import wraps
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import binascii

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash

from tasks import send_notification_email
from repositories import DuplicateUserError, TaskRepository, UserRepository, initialize_database


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("SECRET_KEY", secrets.token_hex(32))
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "3600"))


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the schema and migrate databases made by older API versions."""
    initialize_database(DATABASE)


def _encode(value):
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(
        json.dumps(
            {"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL},
            separators=(",", ":"),
        ).encode()
    )
    message = f"{header}.{payload}".encode("ascii")
    signature = _encode(hmac.new(JWT_SECRET.encode(), message, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def verify_token(token):
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}".encode("ascii")
        expected = _encode(hmac.new(JWT_SECRET.encode(), message, hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_decode(payload))
        if claims.get("exp", 0) < time.time() or not isinstance(claims.get("sub"), int):
            return None
        return claims["sub"]
    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
    ):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = verify_token(token) if scheme.lower() == "bearer" and token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        user = UserRepository(DATABASE).get(user_id)
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def serialize_task(row):
    return {"id": row["id"], "title": row["title"], "status": row["status"], "created_at": row["created_at"]}


def json_body():
    return request.get_json(silent=True) or {}


@app.route("/auth/register", methods=["POST"])
def register():
    data = json_body()
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        user_id = UserRepository(DATABASE).create(username, password)
    except DuplicateUserError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = json_body()
    user = UserRepository(DATABASE).get_by_username(data.get("username"))
    if user is None or not isinstance(data.get("password"), str) or not check_password_hash(user["password_hash"], data["password"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    title = json_body().get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    created_at = datetime.now(timezone.utc).isoformat()
    row = TaskRepository(DATABASE).create(title.strip(), "pending", created_at, g.current_user["id"])
    return jsonify(serialize_task(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    rows = TaskRepository(DATABASE).list_for_owner(g.current_user["id"])
    return jsonify([serialize_task(row) for row in rows])


def find_task(task_id):
    return TaskRepository(DATABASE).get_for_owner(task_id, g.current_user["id"])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    row = find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(serialize_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = json_body()
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400
    row = find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    title, status = data.get("title", row["title"]), data.get("status", row["status"])
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title must be a non-empty string"}), 400
    if not isinstance(status, str) or not status.strip():
        return jsonify({"error": "status must be a non-empty string"}), 400
    status_changed_to_completed = (
        row["status"] != "completed" and status.strip() == "completed"
    )
    updated = TaskRepository(DATABASE).update_for_owner(
        task_id, g.current_user["id"], title=title.strip(), status=status.strip()
    )
    if status_changed_to_completed:
        try:
            # The current auth model uses username as the owner's contact address.
            send_notification_email.delay(g.current_user["username"], updated["title"])
        except Exception:
            # Redis availability must not make the task update endpoint fail.
            app.logger.exception("Unable to enqueue task completion notification")
    return jsonify(serialize_task(updated))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
