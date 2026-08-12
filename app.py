"""A small Flask API for managing tasks."""

from datetime import datetime, timezone
import base64
import binascii
import hashlib
import hmac
import json
import os
import sqlite3
from sqlite3 import IntegrityError
from functools import wraps

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from celery_config import send_notification_email
from repositories import TaskRepository, UserRepository, initialize_database


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_SECONDS"] = int(os.environ.get("JWT_EXPIRATION_SECONDS", "3600"))


def get_db():
    """Open the configured SQLite database with dictionary-like rows."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def _encode_part(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_part(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(
        json.dumps(
            {
                "sub": str(user_id),
                "exp": int(datetime.now(timezone.utc).timestamp()) + app.config["JWT_EXPIRATION_SECONDS"],
            },
            separators=(",", ":"),
        ).encode()
    )
    message = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(app.config["JWT_SECRET"].encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode_part(signature)}"


def get_authenticated_user_id():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    parts = authorization[7:].split(".")
    if len(parts) != 3:
        return None
    try:
        message = f"{parts[0]}.{parts[1]}".encode("ascii")
        expected = hmac.new(app.config["JWT_SECRET"].encode(), message, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode_part(parts[2])):
            return None
        header = json.loads(_decode_part(parts[0]))
        payload = json.loads(_decode_part(parts[1]))
        if header.get("alg") != "HS256" or int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            return None
        return int(payload["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = get_authenticated_user_id()
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    with get_db() as connection:
        initialize_database(connection)
        try:
            user_id = UserRepository(connection).create(
                {"username": username, "password_hash": generate_password_hash(password)}
            )
            connection.commit()
        except IntegrityError:
            return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401
    with get_db() as connection:
        initialize_database(connection)
        user = UserRepository(connection).find_by_username(username.strip())
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


def task_from_row(row):
    return dict(row)


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task(user_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        # The schema is created lazily when the first task is inserted.
        initialize_database(connection)
        row = TaskRepository(connection).create_for_owner(title, created_at, user_id)
        connection.commit()
    return jsonify(task_from_row(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user_id):
    with get_db() as connection:
        initialize_database(connection)
        rows = TaskRepository(connection).list_for_owner(user_id)
    return jsonify([task_from_row(row) for row in rows])


def find_task(task_id, user_id):
    with get_db() as connection:
        initialize_database(connection)
        return TaskRepository(connection).find_for_owner(task_id, user_id)


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user_id, task_id):
    row = find_task(task_id, user_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_from_row(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user_id, task_id):
    data = request.get_json(silent=True) or {}
    fields = []
    values = []
    updates = {}
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        fields.append("title = ?")
        title = data["title"].strip()
        values.append(title)
        updates["title"] = title
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status must be a non-empty string"}), 400
        fields.append("status = ?")
        status = data["status"].strip()
        values.append(status)
        updates["status"] = status
    if not fields:
        return jsonify({"error": "title or status is required"}), 400

    with get_db() as connection:
        initialize_database(connection)
        repository = TaskRepository(connection)
        existing = repository.find_with_owner_for_update(task_id, user_id)
        if existing is None:
            return jsonify({"error": "task not found"}), 404
        changed, row = repository.update_and_get_for_owner(task_id, user_id, updates)
        if changed == 0:
            return jsonify({"error": "task not found"}), 404
        connection.commit()
    status_changed_to_completed = (
        existing["status"] != "completed" and row["status"] == "completed"
    )
    if status_changed_to_completed:
        send_notification_email.delay(existing["user_email"], row["title"])
    return jsonify(task_from_row(row))


if __name__ == "__main__":
    app.run(debug=True)
