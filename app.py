"""
Task management API with JWT authentication.

A single-file Flask app with clean structure: models, routes, error handling.
Users register/login to receive a JWT, and all /tasks/* endpoints require it.
"""

from datetime import datetime, timezone
from functools import wraps
import os

from flask import Flask, g, jsonify, request
import jwt
from werkzeug.security import check_password_hash

from repositories import (
    TaskRepository,
    UserRepository,
    init_db,
    migrate,
)
from tasks import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-secret-key-change-me-0123456789abcdef"
)
JWT_ALGORITHM = "HS256"

user_repository = UserRepository()
task_repository = TaskRepository()


# ── Auth helpers ──────────────────────────────────────────────

def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=JWT_ALGORITHM)


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[JWT_ALGORITHM])
        except jwt.InvalidTokenError:
            return jsonify({"error": "missing or invalid token"}), 401
        g.user_id = int(payload["sub"])
        return f(*args, **kwargs)

    return wrapper


# ── Auth routes ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repository.get_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = user_repository.create(username, password)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repository.get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"])
    return jsonify({"token": token, "user_id": user["id"]})


# ── Task routes ───────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    return jsonify(task_repository.list_for_owner(g.user_id))


@app.route("/tasks", methods=["POST"])
@token_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create(g.user_id, title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def show_task(task_id: int):
    task = task_repository.get_for_owner(g.user_id, task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    previous = task_repository.get_for_owner(g.user_id, task_id)
    if previous is None:
        return jsonify({"error": "task not found"}), 404
    task = task_repository.update_for_owner(
        g.user_id,
        task_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task["status"] == "completed" and previous["status"] != "completed":
        user_email = user_repository.get_email(g.user_id)
        if user_email is not None:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    migrate()
    app.run(debug=True)
