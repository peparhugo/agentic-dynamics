"""Flask API for managing tasks stored in SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
from werkzeug.security import check_password_hash, generate_password_hash
from tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_LIFETIME = timedelta(hours=1)


def rate_limit_key() -> str:
    """Use the authenticated subject when available, otherwise the client IP."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        try:
            payload = jwt.decode(
                header[7:].strip(), JWT_SECRET, algorithms=[JWT_ALGORITHM]
            )
            user_id = payload.get("sub")
            if isinstance(user_id, str) and user_id.isdigit():
                return f"user:{user_id}"
        except jwt.InvalidTokenError:
            pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    default_limits=["100 per minute"],
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0"),
    headers_enabled=True,
    in_memory_fallback=["100 per minute"],
    in_memory_fallback_enabled=True,
)


def init_db():
    UserRepository(DATABASE).initialize_database(
        generate_password_hash(os.urandom(16).hex())
    )


# ── Models ────────────────────────────────────────────────────

def create_task(title: str, owner_id: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    task_id = TaskRepository(DATABASE).create_task(title, owner_id, now)
    return {"id": task_id, "title": title, "status": "pending", "created_at": now}


def get_tasks(owner_id: int):
    return TaskRepository(DATABASE).get_tasks(owner_id)


def get_tasks_page(owner_id: int, cursor: int | None, limit: int):
    return TaskRepository(DATABASE).get_tasks_page(owner_id, cursor, limit)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return TaskRepository(DATABASE).get_task(task_id, owner_id)


def get_user_email(user_id: int) -> str | None:
    return UserRepository(DATABASE).get_email(user_id)


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    values = {key: value for key, value in (("title", title), ("status", status)) if value is not None}
    return TaskRepository(DATABASE).update_task(task_id, owner_id, values)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        token = header[7:].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if not isinstance(user_id, str) or not user_id.isdigit():
                raise jwt.InvalidTokenError
            user_id = int(user_id)
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid or expired token"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    username, password = data.get("username"), data.get("password")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400
    username = username.strip()
    email = email.strip() if isinstance(email, str) else None
    user_id = UserRepository(DATABASE).create_user(
        username, generate_password_hash(password), email
    )
    if user_id is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    username, password = data.get("username"), data.get("password")
    user = UserRepository(DATABASE).get_by_username(username)
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) + JWT_LIFETIME},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return jsonify({"token": token})

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user_id):
    raw_limit = request.args.get("limit", "20")
    raw_cursor = request.args.get("cursor")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400
    if not 1 <= limit <= 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400
    cursor = None
    if raw_cursor is not None:
        try:
            cursor = int(raw_cursor)
        except (TypeError, ValueError):
            return jsonify({"error": "cursor must be an integer"}), 400
        if cursor < 1:
            return jsonify({"error": "cursor must be a positive integer"}), 400

    tasks, total = get_tasks_page(user_id, cursor, limit)
    next_cursor = None
    if len(tasks) > limit:
        tasks = tasks[:limit]
        next_cursor = str(tasks[-1]["id"])
    return jsonify({"data": tasks, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task(user_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    title = data.get("title")
    if not isinstance(title, str):
        title = ""
    title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(user_id, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(user_id, task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    previous_task = get_task(task_id, user_id)
    if previous_task is None:
        return jsonify({"error": "task not found"}), 404
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data and not isinstance(data["title"], str):
        return jsonify({"error": "title must be a string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    task = update_task(
        task_id, user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        user_email = get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


@app.errorhandler(429)
def rate_limit_exceeded(error):
    return jsonify({"error": "rate limit exceeded"}), 429


# Ensure the database is usable when the application is imported by a WSGI
# server or a test runner, not only when this module is executed as a script.
init_db()


if __name__ == "__main__":
    app.run(debug=True)
