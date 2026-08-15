import logging
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from threading import RLock

import jwt
from flask import Flask, g, jsonify, request
from jwt import InvalidTokenError

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository


app = Flask(__name__)
logger = logging.getLogger(__name__)
app.config.update(
    DATA_FILE=os.environ.get("TASKS_FILE", "tasks.json"),
    USER_DATA_FILE=os.environ.get("USERS_FILE"),
    JWT_SECRET=os.environ.get("JWT_SECRET", os.urandom(32).hex()),
    JWT_EXPIRATION_SECONDS=3600,
)

_storage_lock = RLock()


def _data_file() -> Path:
    return Path(app.config["DATA_FILE"])


def _users_file() -> Path:
    configured = app.config.get("USER_DATA_FILE")
    if configured:
        return Path(configured)
    task_file = _data_file()
    return task_file.with_name(f"{task_file.stem}.users.json")


task_repository = TaskRepository(_data_file, _storage_lock)
user_repository = UserRepository(_users_file, _storage_lock)


def init_storage() -> None:
    """Create stores and migrate tasks written before ownership was added."""
    task_repository.initialize()
    user_repository.initialize()


@app.before_request
def ensure_storage_initialized() -> None:
    init_storage()


def _issue_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"]),
    }
    return jwt.encode(payload, app.config["JWT_SECRET"], algorithm="HS256")


def require_auth(view):
    @wraps(view)
    def authenticated_view(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(
                token, app.config["JWT_SECRET"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid token"}), 401

        if user_repository.get_by_id(user_id) is None:
            return jsonify({"error": "invalid token"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return authenticated_view


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _credentials() -> tuple[str, str] | None:
    data = _json_body()
    if data is None:
        return None
    username = data.get("username")
    password = data.get("password")
    if (
        not isinstance(username, str)
        or not username.strip()
        or not isinstance(password, str)
        or not password
    ):
        return None
    return username.strip(), password


@app.post("/auth/register")
def register():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    user = user_repository.create_user(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.post("/auth/login")
def login():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repository.authenticate(*credentials)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": _issue_token(user["id"])})


@app.get("/tasks")
@require_auth
def list_tasks():
    return jsonify(task_repository.list_for_owner(g.user_id))


@app.post("/tasks")
@require_auth
def add_task():
    data = _json_body()
    title = data.get("title") if data is not None else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(task_repository.create_for_owner(title.strip(), g.user_id)), 201


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(task_id: int):
    task = task_repository.get_for_owner(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def edit_task(task_id: int):
    existing_task = task_repository.get_for_owner(task_id, g.user_id)
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404

    data = _json_body()
    if data is None:
        return jsonify({"error": "JSON object is required"}), 400
    if "title" in data and (
        not isinstance(data["title"], str) or not data["title"].strip()
    ):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    title = data["title"].strip() if "title" in data else None
    task = task_repository.update_for_owner(
        task_id, g.user_id, title=title, status=data.get("status")
    )
    if existing_task["status"] != "completed" and task["status"] == "completed":
        owner = user_repository.get_by_id(g.user_id)
        try:
            send_notification_email.delay(owner["username"], task["title"])
        except Exception:
            logger.exception("Could not queue completion notification for task %s", task_id)
    return jsonify(task)


@app.errorhandler(404)
def route_not_found(_error):
    return jsonify({"error": "not found"}), 404


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
