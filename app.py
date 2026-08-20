"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Now with JWT authentication: users own their tasks.
"""

from flask import Flask, request, jsonify
from functools import wraps
import sqlite3
import os

import jwt as pyjwt
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from tasks import send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me-in-production-0123456789")
JWT_ALGORITHM = "HS256"
RATE_LIMIT_STORAGE_URI = os.environ.get(
    "RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/0"
)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ── Repositories ──────────────────────────────────────────────

user_repository = UserRepository(get_db)
task_repository = TaskRepository(get_db)


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
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
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        conn.commit()
    migrate()


def migrate():
    """Add missing columns (owner_id, email) without breaking existing data."""
    with get_db() as conn:
        task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in task_columns:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


# ── Auth helpers ──────────────────────────────────────────────

def make_token(user_id: int, username: str) -> str:
    payload = {"sub": str(user_id), "username": username}
    return pyjwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def current_user() -> dict | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[len("Bearer "):].strip()
    try:
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except pyjwt.PyJWTError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return user_repository.find_by_id(int(user_id))


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "unauthorized"}), 401
        return fn(user, *args, **kwargs)

    return wrapper


# ── Rate limiting ─────────────────────────────────────────────

def rate_limit_key() -> str:
    """Key authenticated requests by user, everything else by client address."""
    user = current_user()
    if user is not None:
        return f"user:{user['id']}"
    return get_remote_address()


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=["100 per minute"],
    headers_enabled=True,
    strategy="fixed-window",
)

app.config.setdefault("RATELIMIT_STORAGE_URI", RATE_LIMIT_STORAGE_URI)
limiter.init_app(app)


# ── Auth routes ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip() or None
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repository.find_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = user_repository.create(username, generate_password_hash(password), email)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = user_repository.find_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = make_token(user["id"], user["username"])
    return jsonify({"token": token})


# ── Task routes ───────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user):
    cursor = request.args.get("cursor")
    if cursor is not None:
        try:
            cursor = int(cursor)
        except (TypeError, ValueError):
            cursor = None
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    limit = max(1, min(100, limit))
    return jsonify(task_repository.find_page(user["id"], cursor, limit))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task(user):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create(title, user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(user, task_id: int):
    task = task_repository.find_by_id_and_owner(task_id, user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(user, task_id: int):
    data = request.get_json(silent=True) or {}
    previous = task_repository.find_by_id_and_owner(task_id, user["id"])
    task = task_repository.update(
        task_id,
        user["id"],
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        data.get("status") == "completed"
        and (previous is None or previous.get("status") != "completed")
    ):
        user_email = user.get("email") or f"{user['username']}@example.com"
        try:
            send_notification_email.delay(user_email, task["title"])
        except Exception:
            app.logger.exception("Failed to enqueue notification email")
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
