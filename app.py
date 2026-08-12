"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.

Session 2: JWT authentication added.
  - New User model (id, username, password_hash)
  - POST /auth/register and POST /auth/login
  - All /tasks/* endpoints require a valid JWT
  - Each user only sees their own tasks (Task.owner_id)

Session 3: Async email notifications.
  - Celery + Redis for background jobs
  - When a task transitions to 'completed', enqueue send_notification_email
    to the task owner (email is optional on register, defaults to
    <username>@example.com)

Session 4: Repository pattern.
  - All SQLite access moved into repository classes (repositories.py)
  - Route handlers call repository methods, never raw SQL
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import jwt

from flask_limiter import Limiter

from tasks import send_notification_email

from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
TOKEN_TTL_HOURS = 24

# Pagination defaults for GET /tasks
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Rate limiting configuration. Redis is the storage backend; the connection
# can be pointed elsewhere via RATE_LIMIT_STORAGE (or swapped for a test
# double by passing storage_options to create_limiter).
RATE_LIMIT_STORAGE = os.environ.get(
    "RATE_LIMIT_STORAGE", "redis://localhost:6379/0"
)
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "100"))
RATE_LIMIT_KEY_PREFIX = "task_api"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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
            "  owner_id INTEGER"
            ")"
        )
        # Migration: add owner_id to pre-existing tasks tables without it.
        cols = [row[1] for row in conn.execute("PRAGMA table_info(tasks)")]
        if "owner_id" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        # Migration: add email to pre-existing users tables without it.
        user_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
        if "email" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


# ── Repositories ────────────────────────────────────────────


task_repo = TaskRepository(get_db)
user_repo = UserRepository(get_db)


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    import re
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated

# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


def generate_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        return None


# ── Rate limiting ─────────────────────────────────────────────


def get_rate_limit_key() -> str:
    """Identify the caller for rate limiting.

    Authenticated callers are keyed by their user id (from the JWT), so each
    user gets their own 100 requests/minute budget. Unauthenticated callers
    (e.g. register/login) fall back to their client IP.
    """
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
    user_id = decode_token(token) if token else None
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{request.remote_addr}"


def create_limiter(storage_uri: str | None = None, storage_options: dict | None = None) -> Limiter:
    """Build the application-wide rate limiter.

    Uses Flask-Limiter with Redis as the storage backend. A single
    application-level budget of ``RATE_LIMIT_PER_MINUTE`` requests per minute
    is shared across ALL endpoints (including auth), per caller.
    """
    return Limiter(
        key_func=get_rate_limit_key,
        application_limits=[f"{RATE_LIMIT_PER_MINUTE} per minute"],
        storage_uri=storage_uri or RATE_LIMIT_STORAGE,
        storage_options=storage_options,
        headers_enabled=True,
        key_prefix=RATE_LIMIT_KEY_PREFIX,
    )


limiter = create_limiter()


def notify_task_completed(owner_id: int, task_title: str) -> None:
    """Enqueue an async notification email to the task owner.

    Dispatch is non-blocking: the task is sent to Celery (Redis broker)
    and the API response returns immediately.
    """
    user = user_repo.get_user(owner_id)
    if user is None:
        return
    user_email = user.get("email") or f"{user['username']}@example.com"
    send_notification_email.delay(user_email, task_title)


# ── Auth helpers ──────────────────────────────────────────────


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
        user_id = decode_token(token) if token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return wrapper


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repo.get_user_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 400
    user = user_repo.create_user(username, password)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user = user_repo.get_user_by_username(username)
    if user is None or not user_repo.verify_password(user, password):
        return jsonify({"error": "invalid credentials"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    """Cursor-paginated task listing.

    Query params: ``?cursor=<id>&limit=<n>`` (default limit=20, max=100).
    ``cursor`` is the id of the last item on the previous page; omitting it
    returns the first page. Response is ``{data, next_cursor, total}``.
    """
    cursor_raw = request.args.get("cursor")
    cursor = None
    if cursor_raw is not None:
        try:
            cursor = int(cursor_raw)
        except (TypeError, ValueError):
            cursor = None

    try:
        limit = int(request.args.get("limit", DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        limit = DEFAULT_PAGE_SIZE
    if limit < 1:
        limit = DEFAULT_PAGE_SIZE
    limit = min(limit, MAX_PAGE_SIZE)

    data, next_cursor, total = task_repo.get_tasks_paginated(
        g.user_id, cursor=cursor, limit=limit
    )
    return jsonify({"data": data, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create_task(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repo.get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    previous = task_repo.get_task(task_id, g.user_id)
    task = task_repo.update_task(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        task["status"] == "completed"
        and (previous is None or previous["status"] != "completed")
    ):
        notify_task_completed(g.user_id, task["title"])
    return jsonify(task)


limiter.init_app(app)

init_db()


if __name__ == "__main__":
    app.run(debug=True)
