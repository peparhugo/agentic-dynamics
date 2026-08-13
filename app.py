import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import (
    BaseRepository,
    DuplicateUserError,
    TaskRepository,
    UserRepository,
)


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_LIFETIME = timedelta(hours=1)


def init_db():
    BaseRepository.initialize_database(DATABASE)


def users():
    return UserRepository(DATABASE)


def tasks():
    return TaskRepository(DATABASE)


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def error(message, status_code):
    return jsonify({"error": message}), status_code


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return error("authentication required", 401)

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return error("invalid token", 401)

        user = users().get_by_id(user_id)
        if user is None:
            return error("invalid token", 401)
        return view(user_id, *args, **kwargs)

    return wrapped


def credentials():
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


@app.post("/auth/register")
def register():
    values = credentials()
    if values is None:
        return error("username and password are required", 400)
    username, password = values

    try:
        user_id = users().create_user(username, generate_password_hash(password))
    except DuplicateUserError:
        return error("username already exists", 409)

    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    values = credentials()
    if values is None:
        return error("username and password are required", 400)
    username, password = values

    user = users().get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("invalid credentials", 401)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user["id"]), "iat": now, "exp": now + JWT_LIFETIME},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return jsonify({"token": token})


@app.post("/tasks")
@require_auth
def create_task(user_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("title is required", 400)

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return error("title is required", 400)

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    task_id = tasks().create_for_owner(title, created_at, user_id)

    return jsonify(
        {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }
    ), 201


@app.get("/tasks")
@require_auth
def list_tasks(user_id):
    rows = tasks().list_for_owner(user_id)
    return jsonify([task_json(row) for row in rows])


@app.get("/tasks/<int:task_id>")
@require_auth
def get_task(user_id, task_id):
    row = tasks().get_for_owner(task_id, user_id)
    if row is None:
        return error("task not found", 404)
    return jsonify(task_json(row))


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(user_id, task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("JSON object is required", 400)

    updates = {}

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            return error("title must be a non-empty string", 400)
        updates["title"] = title.strip()

    if "status" in data:
        status = data["status"]
        if not isinstance(status, str) or not status.strip():
            return error("status must be a non-empty string", 400)
        updates["status"] = status.strip()

    if not updates:
        return error("title or status is required", 400)

    existing, row = tasks().update_for_owner(task_id, user_id, **updates)
    if existing is None:
        return error("task not found", 404)

    if existing["status"] != "completed" and row["status"] == "completed":
        send_notification_email.delay(existing["owner_email"], row["title"])

    return jsonify(task_json(row))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
