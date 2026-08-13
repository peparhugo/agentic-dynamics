"""
Task Management Flask API

A simple REST API for managing tasks with SQLite persistence.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from celery_tasks import celery, send_notification_email
from repository import Database, UserRepository, TaskRepository

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")


def get_db():
    """Get database instance with current DATABASE path."""
    return Database(DATABASE)


def get_user_repository():
    """Get user repository with current DATABASE path."""
    return UserRepository(DATABASE)


def get_task_repository():
    """Get task repository with current DATABASE path."""
    return TaskRepository(DATABASE)


def init_db():
    """Initialize the database schema."""
    get_db().init_schema()


def generate_token(user_id):
    """Generate JWT token for user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token):
    """Verify JWT token and return user_id."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except jwt.InvalidTokenError:
        return None


def get_user_email(user_id):
    """Get user email by user_id."""
    return get_user_repository().get_email(user_id)


def auth_required(f):
    """Decorator to protect endpoints with JWT authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401

        token = auth_header[7:]
        user_id = verify_token(token)

        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401

        return f(user_id, *args, **kwargs)

    return decorated_function


@app.route("/auth/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()

    if not username:
        return jsonify({"error": "username is required"}), 400

    if not password:
        return jsonify({"error": "password is required"}), 400

    password_hash = generate_password_hash(password)

    try:
        user_id = get_user_repository().create(username, password_hash, email)
    except ValueError:
        return jsonify({"error": "username already exists"}), 409

    token = generate_token(user_id)
    return jsonify({
        "user_id": user_id,
        "username": username,
        "token": token
    }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    """Login user and return JWT token."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = get_user_repository().read_by_username(username)

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401

    user_id = user["id"]
    token = generate_token(user_id)
    return jsonify({
        "user_id": user_id,
        "username": username,
        "token": token
    }), 200


@app.route("/tasks", methods=["POST"])
@auth_required
def create_task(user_id):
    """Create a new task."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    now = datetime.utcnow().isoformat()
    task_id = get_task_repository().create(title, "pending", now, user_id)

    return jsonify({
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": now,
        "owner_id": user_id
    }), 201


@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks(user_id):
    """List all tasks for the authenticated user ordered by created_at descending."""
    tasks = get_task_repository().read_by_owner(user_id)
    return jsonify(tasks)


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def get_task(user_id, task_id):
    """Get a single task by ID."""
    task = get_task_repository().read(task_id, user_id)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def update_task(user_id, task_id):
    """Update task title and/or status."""
    data = request.get_json(silent=True) or {}

    task = get_task_repository().read(task_id, user_id)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    old_status = task["status"]

    # Update title only if provided and not empty
    if "title" in data:
        stripped_title = data.get("title", "").strip()
        if stripped_title:
            title = stripped_title
        else:
            title = task["title"]
    else:
        title = task["title"]

    status = data.get("status", task["status"])

    get_task_repository().update(task_id, title=title, status=status)

    task["title"] = title
    task["status"] = status

    # Trigger async email notification if status changed to completed
    if old_status != "completed" and status == "completed":
        user_email = get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, title)

    return jsonify(task)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
