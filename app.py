"""Flask API for managing user-owned tasks stored in SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import (
    BaseRepository,
    DuplicateUsernameError,
    TaskRepository,
    UserRepository,
)


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "development-secret-key")
app.config["JWT_EXPIRATION_HOURS"] = 24


def init_db():
    BaseRepository.initialize_database(app.config["DATABASE"])


def user_repository():
    return UserRepository(app.config["DATABASE"])


def task_repository():
    return TaskRepository(app.config["DATABASE"])


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def error(message, status_code):
    return jsonify({"error": message}), status_code


def issue_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256")


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return error("authentication required", 401)
        try:
            payload = jwt.decode(
                token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return error("invalid or expired token", 401)

        user = user_repository().find_by_id(user_id)
        if user is None:
            return error("invalid or expired token", 401)
        g.user = user
        return view(*args, **kwargs)

    return wrapped


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    email = data.get("email") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip():
        return error("username is required", 400)
    if not isinstance(password, str) or not password:
        return error("password is required", 400)
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return error("email must be a non-empty string", 400)

    username = username.strip()
    try:
        user_id = user_repository().create_user(
            username, email.strip() if email else None, generate_password_hash(password)
        )
    except DuplicateUsernameError:
        return error("username already exists", 409)
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not isinstance(password, str):
        return error("username and password are required", 400)

    user = user_repository().find_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("invalid username or password", 401)
    return jsonify({"token": issue_token(user["id"]), "username": user["username"]})


@app.route("/tasks", methods=["POST"])
@authenticated
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return error("title is required", 400)

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    row = task_repository().create_task(title, created_at, g.user["id"])
    return jsonify(task_json(row)), 201


@app.route("/tasks", methods=["GET"])
@authenticated
def list_tasks():
    rows = task_repository().list_for_owner(g.user["id"])
    return jsonify([task_json(row) for row in rows])


def find_task(task_id):
    return task_repository().find_for_owner(task_id, g.user["id"])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@authenticated
def get_task(task_id):
    row = find_task(task_id)
    if row is None:
        return error("task not found", 404)
    return jsonify(task_json(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@authenticated
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("request body must be a JSON object", 400)

    fields = []
    values = []
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return error("title must be a non-empty string", 400)
        fields.append("title = ?")
        values.append(data["title"].strip())
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return error("status must be a non-empty string", 400)
        fields.append("status = ?")
        values.append(data["status"].strip())
    if not fields:
        return error("title or status is required", 400)

    previous_row = find_task(task_id)
    if previous_row is None:
        return error("task not found", 404)
    status_changed_to_completed = (
        data.get("status") == "completed" and previous_row["status"] != "completed"
    )

    row = task_repository().update_for_owner(
        task_id,
        g.user["id"],
        {field.split(" = ")[0]: value for field, value in zip(fields, values)},
    )
    if row is None:
        return error("task not found", 404)
    if status_changed_to_completed:
        send_notification_email.delay(
            g.user["email"] or g.user["username"], row["title"]
        )
    return jsonify(task_json(row))


# Initialize the schema when the application module starts.
init_db()


if __name__ == "__main__":
    app.run(debug=True)
