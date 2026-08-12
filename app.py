"""JWT-authenticated task management API backed by SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email
from repositories import (
    TaskRepository,
    UserRepository,
    UsernameAlreadyExistsError,
    init_database,
)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["TOKEN_TTL_SECONDS"] = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))
DATABASE = os.environ.get("DATABASE", "tasks.db")


def init_db():
    """Create the schema and migrate databases created by older versions."""
    init_database(DATABASE)


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def issue_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=app.config["TOKEN_TTL_SECONDS"]),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def authenticate_request(view):
    @wraps(view)
    def protected(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        token = header[7:].strip()
        if not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid token"}), 401

        user = UserRepository(DATABASE).get(user_id)
        if user is None:
            return jsonify({"error": "invalid token"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return protected


def task_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


@app.post("/auth/register")
def register():
    data = json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400

    username = username.strip()
    try:
        user_id = UserRepository(DATABASE).create(
            {"username": username, "password_hash": generate_password_hash(password)}
        )
    except UsernameAlreadyExistsError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    data = json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401

    user = UserRepository(DATABASE).find_by_username(username.strip())
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": issue_token(user["id"]), "username": user["username"]})


@app.post("/tasks")
@authenticate_request
def create_task():
    data = json_body()
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    status = data.get("status", "pending")
    if not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400

    repository = TaskRepository(DATABASE)
    task_id = repository.create(
        {
            "title": title.strip(),
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": g.current_user["id"],
        }
    )
    row = repository.get(task_id)
    return jsonify(task_dict(row)), 201


@app.get("/tasks")
@authenticate_request
def list_tasks():
    rows = TaskRepository(DATABASE).list_for_owner(g.current_user["id"])
    return jsonify([task_dict(row) for row in rows])


def find_task(task_id):
    return TaskRepository(DATABASE).find_for_owner(task_id, g.current_user["id"])


@app.get("/tasks/<int:task_id>")
@authenticate_request
def get_task(task_id):
    row = find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_dict(row))


@app.put("/tasks/<int:task_id>")
@authenticate_request
def update_task(task_id):
    data = json_body()
    supplied_fields = {field for field in ("title", "status") if field in data}
    if not supplied_fields:
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        data["title"] = data["title"].strip()
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    should_notify = False
    notification_email = None
    notification_title = None
    repository = TaskRepository(DATABASE)
    row = repository.find_for_owner(task_id, g.current_user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    new_status = data.get("status", row["status"])
    should_notify = row["status"] != "completed" and new_status == "completed"
    notification_email = g.current_user["username"]
    notification_title = data.get("title", row["title"])
    updated = repository.update_for_owner(
        task_id,
        g.current_user["id"],
        {"title": data.get("title", row["title"]), "status": new_status},
    )
    if should_notify:
        try:
            send_notification_email.delay(notification_email, notification_title)
        except Exception:
            # A broker outage must not turn a successful task update into an API error.
            app.logger.exception("Unable to queue task completion notification")
    return jsonify(task_dict(updated))


init_db()


if __name__ == "__main__":
    app.run()
