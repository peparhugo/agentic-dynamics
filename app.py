"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import jwt
import sqlite3
import os
from celery_config import celery_app
from tasks import send_notification_email
from repositories import UserRepository, TaskRepository
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from redis import Redis

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE = os.environ.get("DATABASE", "todos.db")

redis_client = None
if not app.config.get("TESTING", False):
    try:
        redis_client = Redis(host=os.environ.get("REDIS_HOST", "localhost"), port=int(os.environ.get("REDIS_PORT", 6379)), decode_responses=True, socket_connect_timeout=1)
        redis_client.ping()
    except Exception:
        redis_client = None


def get_rate_limit_key():
    """Get the rate limit key: user_id for authenticated requests, IP for others."""
    if "Authorization" in request.headers:
        auth_header = request.headers["Authorization"]
        try:
            token = auth_header.split(" ")[1]
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            return f"user:{data['user_id']}"
        except (IndexError, jwt.InvalidTokenError):
            pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    app=app,
    key_func=get_rate_limit_key,
    storage_uri="memory://" if (app.config.get("TESTING", False) or redis_client is None) else "redis://localhost:6379",
    default_limits=["100 per minute"],
    enabled=not app.config.get("TESTING", False),
)


def get_repositories():
    """Get repository instances."""
    return UserRepository(DATABASE), TaskRepository(DATABASE)

# Initialize Celery with Flask app context
def make_celery(app):
    celery = celery_app
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT UNIQUE NOT NULL,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER NOT NULL,"
            "  FOREIGN KEY (owner_id) REFERENCES users(id)"
            ")"
        )
        conn.commit()


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"error": "invalid authorization header"}), 401

        if not token:
            return jsonify({"error": "missing authorization token"}), 401

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user_id = data["user_id"]
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401

        return f(current_user_id, *args, **kwargs)

    return decorated


# ── Auth Helpers ─────────────────────────────────────────────

def generate_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


# ── Routes ─────────────────────────────────────────────────────

# Auth endpoints

@app.route("/auth/register", methods=["POST"])
@limiter.limit("100 per minute")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip() or None

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user_repo, _ = get_repositories()
    user = user_repo.create(username, password, email=email)
    if user is None:
        return jsonify({"error": "username already exists"}), 400

    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
@limiter.limit("100 per minute")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user_repo, _ = get_repositories()
    user = user_repo.get_by_username(username)
    if user is None or not user_repo.verify_password(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    token = generate_token(user["id"])
    return jsonify({
        "token": token,
        "user_id": user["id"],
        "username": user["username"],
        "email": user.get("email"),
    }), 200


# Task endpoints (protected)

@app.route("/tasks", methods=["GET"])
@limiter.limit("100 per minute")
@token_required
def list_tasks(current_user_id):
    _, task_repo = get_repositories()
    cursor = request.args.get("cursor", type=int)
    limit = request.args.get("limit", default=20, type=int)

    # Validate limit
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100

    tasks, total_count, next_cursor = task_repo.get_paginated_by_owner(current_user_id, cursor, limit)
    return jsonify({
        "data": tasks,
        "next_cursor": next_cursor,
        "total": total_count,
    })


@app.route("/tasks", methods=["POST"])
@limiter.limit("100 per minute")
@token_required
def add_task(current_user_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    _, task_repo = get_repositories()
    task = task_repo.create(title, current_user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@limiter.limit("100 per minute")
@token_required
def show_task(current_user_id, task_id: int):
    _, task_repo = get_repositories()
    task = task_repo.get_by_id(task_id, current_user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@limiter.limit("100 per minute")
@token_required
def edit_task(current_user_id, task_id: int):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    user_repo, task_repo = get_repositories()

    # Get current task to check if status is changing to 'completed'
    current_task = task_repo.get_by_id(task_id, current_user_id)
    if current_task is None:
        return jsonify({"error": "task not found"}), 404

    # Update the task
    task = task_repo.update(
        task_id,
        current_user_id,
        title=data.get("title"),
        status=new_status,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404

    # Trigger email notification if status changed to 'completed'
    if new_status == "completed" and current_task.get("status") != "completed":
        user = user_repo.get_by_id(current_user_id)
        if user and user.get("email"):
            send_notification_email.delay(user["email"], task["title"])

    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
