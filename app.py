"""Flask API for managing user-owned tasks stored in SQLite."""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, jsonify, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "development-secret")
app.config["JWT_EXPIRATION_HOURS"] = 24


def get_db():
    """Create a database connection configured to return mapping-like rows."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create storage and migrate databases created before task ownership."""
    UserRepository(get_db).initialize()
    TaskRepository(get_db).initialize()


def task_response(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def get_task(task_id, owner_id):
    return TaskRepository(get_db).find_by_id_and_owner(task_id, owner_id)


def token_required(view):
    """Require a signed, unexpired Bearer token and expose its user id."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(
                token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
            )
            g.user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    email = data.get("email") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400

    user_id = UserRepository(get_db).create_user(
        username.strip(), generate_password_hash(password), email.strip() if email else None
    )
    if user_id is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username.strip()}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401

    user = UserRepository(get_db).find_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "iat": now,
            "exp": now + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"]),
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    return jsonify({"token": token})


@app.post("/tasks")
@token_required
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    created_at = datetime.now(timezone.utc).isoformat()
    task = TaskRepository(get_db).create_for_owner(title.strip(), created_at, g.user_id)
    return jsonify(task_response(task)), 201


@app.get("/tasks")
@token_required
def list_tasks():
    tasks = TaskRepository(get_db).list_for_owner(g.user_id)
    return jsonify([task_response(task) for task in tasks])


@app.get("/tasks/<int:task_id>")
@token_required
def retrieve_task(task_id):
    task = get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_response(task))


@app.put("/tasks/<int:task_id>")
@token_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body is required"}), 400

    values = {}
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        values["title"] = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str):
            return jsonify({"error": "status must be a string"}), 400
        values["status"] = data["status"]
    if not values:
        return jsonify({"error": "title or status is required"}), 400

    notify_email = None
    existing_task, task = TaskRepository(get_db).update_for_owner(task_id, g.user_id, values)
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404
    if existing_task["status"] != "completed" and task["status"] == "completed":
        notify_email = existing_task["email"]
    if notify_email:
        send_notification_email.delay(notify_email, task["title"])
    return jsonify(task_response(task))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
