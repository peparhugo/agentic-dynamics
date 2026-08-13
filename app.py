"""
Flask Task Management API

A simple task management API with SQLite persistence and JWT authentication.
"""

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from tasks_celery import celery_app, send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)
app.config["CELERY_BROKER_URL"] = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
app.config["CELERY_RESULT_BACKEND"] = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
app.config["TESTING"] = os.environ.get("TESTING", "").lower() == "true"

celery_app.conf.update(app.config)

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/2")
storage_uri = "memory://" if app.config["TESTING"] else redis_url
limiter = Limiter(
    app=app,
    key_func=lambda: _get_rate_limit_key(),
    default_limits=["100/minute"],
    storage_uri=storage_uri,
    strategy="fixed-window",
    in_memory_fallback_enabled=app.config["TESTING"]
)

class ContextTask(celery_app.Task):
    def __call__(self, *args, **kwargs):
        with app.app_context():
            return self.run(*args, **kwargs)

celery_app.Task = ContextTask

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

user_repo = UserRepository()
task_repo = TaskRepository()


# ── Database ────────────────────────────────────────────────────

def init_db():
    user_repo.init_db()
    task_repo.init_db()


# ── Rate Limiting Helpers ────────────────────────────────────

def _get_rate_limit_key():
    """Get rate limit key based on authenticated user or IP address."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        user_id = verify_jwt_token(token)
        if user_id is not None:
            return f"user:{user_id}"
    return f"ip:{get_remote_address()}"


# ── Authentication Helpers ─────────────────────────────────────

def get_jwt_token(user_id):
    """Generate a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_jwt_token(token):
    """Verify and decode a JWT token. Returns user_id or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
        return None


def require_auth(f):
    """Decorator to require JWT authentication on an endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401

        token = auth_header[7:]
        user_id = verify_jwt_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401

        return f(user_id, *args, **kwargs)
    return decorated_function


# ── Helper Functions ────────────────────────────────────────────

def task_to_dict(row):
    """Convert a database row to a dictionary."""
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.errorhandler(429)
def rate_limit_handler(e):
    """Handle rate limit exceeded with Retry-After header."""
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    response.headers["Retry-After"] = "60"
    return response


# ── Authentication Endpoints ────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
@limiter.limit("100/minute")
def register():
    """Register a new user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip() if "email" in data else None

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    password_hash = generate_password_hash(password)

    try:
        user_id = user_repo.create_user(username, password_hash, email)
    except Exception:
        return jsonify({"error": "username already exists"}), 400

    token = get_jwt_token(user_id)
    return jsonify({"token": token}), 201


@app.route("/auth/login", methods=["POST"])
@limiter.limit("100/minute")
def login():
    """Log in a user and return a JWT token."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_repo.get_user_by_username(username)

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    token = get_jwt_token(user["id"])
    return jsonify({"token": token}), 200


# ── Task Endpoints ──────────────────────────────────────────────

@app.route("/tasks", methods=["POST"])
@limiter.limit("100/minute")
@require_auth
def create_task(user_id):
    """Create a new task."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    now = datetime.utcnow().isoformat()
    task_id = task_repo.create_task(title, "pending", now, user_id)

    return jsonify({
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": now,
    }), 201


@app.route("/tasks", methods=["GET"])
@limiter.limit("100/minute")
@require_auth
def list_tasks(user_id):
    """List tasks for the authenticated user with cursor-based pagination."""
    cursor = request.args.get("cursor", type=int)
    limit = request.args.get("limit", default=20, type=int)

    if limit < 1:
        limit = 20
    elif limit > 100:
        limit = 100

    all_rows = task_repo.get_tasks_by_owner(user_id)
    total = len(all_rows)

    if cursor is None:
        start_idx = 0
    else:
        start_idx = next((i + 1 for i, row in enumerate(all_rows) if row["id"] == cursor), 0)

    end_idx = start_idx + limit
    page_rows = all_rows[start_idx:end_idx]

    next_cursor = None
    if end_idx < total and page_rows:
        next_cursor = page_rows[-1]["id"]

    return jsonify({
        "data": [task_to_dict(row) for row in page_rows],
        "next_cursor": next_cursor,
        "total": total
    })


@app.route("/tasks/<int:task_id>", methods=["GET"])
@limiter.limit("100/minute")
@require_auth
def get_task(user_id, task_id):
    """Get a single task by ID."""
    row = task_repo.get_task_by_id_and_owner(task_id, user_id)

    if row is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@limiter.limit("100/minute")
@require_auth
def update_task(user_id, task_id):
    """Update a task's title and/or status."""
    data = request.get_json(silent=True) or {}

    row = task_repo.get_task_by_id_and_owner(task_id, user_id)

    if row is None:
        return jsonify({"error": "task not found"}), 404

    title = data.get("title", row["title"]).strip() if "title" in data else row["title"]
    status = data.get("status", row["status"]) if "status" in data else row["status"]

    if "title" in data and not title:
        return jsonify({"error": "title cannot be empty"}), 400

    old_status = row["status"]
    task_repo.update_task(task_id, title, status)

    if status == "completed" and old_status != "completed":
        user_email = user_repo.get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, title)

    return jsonify({
        "id": task_id,
        "title": title,
        "status": status,
        "created_at": row["created_at"],
    })


@app.route("/health", methods=["GET"])
@limiter.limit("100/minute")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
