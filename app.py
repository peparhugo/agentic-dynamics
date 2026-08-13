"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os
import sqlite3

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION = timedelta(hours=1)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    UserRepository(get_db).initialize()
    TaskRepository(get_db).initialize()


def task_repository() -> TaskRepository:
    return TaskRepository(get_db)


def user_repository() -> UserRepository:
    return UserRepository(get_db)


# ── Routes ─────────────────────────────────────────────────────

def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + JWT_EXPIRATION},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            g.user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid token"}), 401
        return view(*args, **kwargs)

    return wrapped


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400

    username = username.strip()
    email = email.strip() if email is not None else None
    try:
        user_id = user_repository().create_user(
            username, generate_password_hash(password), email
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401

    user = user_repository().find_by_username(username.strip())
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])}), 200

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(task_repository().list_for_owner(g.user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = task_repository().create_task(title.strip(), g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repository().find_for_owner(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    status = data.get("status")
    if title is not None and not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    if isinstance(title, str) and not title.strip():
        return jsonify({"error": "title is required"}), 400
    if status is not None and not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400
    repository = task_repository()
    previous_task = repository.find_for_owner(task_id, g.user_id)
    if previous_task is None:
        return jsonify({"error": "task not found"}), 404
    values = {}
    if title is not None:
        values["title"] = title.strip()
    if status is not None:
        values["status"] = status
    task = repository.update_for_owner(task_id, g.user_id, values)
    if previous_task["status"] != "completed" and task["status"] == "completed":
        user_email = user_repository().notification_address(g.user_id)
        if user_email:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
