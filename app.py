"""Flask API for managing authenticated tasks stored in SQLite."""

from functools import wraps
from flask import Flask, g, jsonify, request
import sqlite3
import os
import time
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
from tasks import send_notification_email
from repositories import TaskRepository, UserRepository, initialize_database

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 3600


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    initialize_database(get_db)


# Initialize the schema when the application module is loaded by a WSGI server.
init_db()


def create_task(title: str, owner_id: int | None = None) -> dict:
    return TaskRepository(get_db).create_task(title, owner_id)


def get_tasks(owner_id: int | None = None):
    return TaskRepository(get_db).list_tasks(owner_id)


def get_task(task_id: int, owner_id: int | None = None) -> dict | None:
    return TaskRepository(get_db).get_task(task_id, owner_id)



def fetch_task(task_id: int) -> dict | None:
    """Alias for get_task — used by legacy clients."""
    return get_task(task_id)



def update_task(task_id: int, title: str | None = None, status: str | None = None,
                owner_id: int | None = None) -> dict | None:
    return TaskRepository(get_db).update_task(task_id, title, status, owner_id)


def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + JWT_EXPIRATION_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def require_auth(view):
    @wraps(view)
    def authenticated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "authorization required"}), 401
        token = header[7:].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid or expired token"}), 401
        user = UserRepository(get_db).get_auth_user(user_id)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user = dict(user)
        return view(*args, **kwargs)
    return authenticated


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        user = UserRepository(get_db).create_user(username, generate_password_hash(password))
        user_id = user["id"]
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    user = UserRepository(get_db).get_by_username(username)
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.user["id"]))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not isinstance(data.get("title"), str):
        return jsonify({"error": "title is required"}), 400
    title = data["title"].strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, g.user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    current_task = get_task(task_id, g.user["id"])
    task = update_task(
        task_id,
        title=data["title"].strip() if "title" in data else None,
        status=data.get("status"),
        owner_id=g.user["id"],
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if current_task["status"] != "completed" and task["status"] == "completed":
        owner = UserRepository(get_db).get_auth_user(task["owner_id"])
        if owner is not None:
            send_notification_email.delay(owner["username"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    app.run(debug=True)
