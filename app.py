"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import os
import jwt

from tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 24

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


def rate_limit_key() -> str:
    """Key rate limits per authenticated user; anonymous requests (e.g.
    register/login) fall back to the client IP since there's no user yet."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return f"user:{payload['user_id']}"
        except jwt.InvalidTokenError:
            pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    storage_uri=REDIS_URL,
    default_limits=[RATE_LIMIT],
    headers_enabled=True,
)


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "rate limit exceeded"}), 429


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        # Migration: existing databases created before auth was added won't
        # have owner_id on tasks. Add it without touching existing rows.
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        conn.commit()


# Repositories are handed the ``get_db`` function itself (not a live
# connection) so a connection is opened fresh — against whatever DATABASE
# currently points at — on every call. This is what lets tests repoint
# app.DATABASE at a temp file per-test without repositories caching a stale
# path or connection.
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


def get_user_by_username(username: str) -> dict | None:
    """Kept as a module-level function for backward compatibility with
    existing callers; delegates to UserRepository."""
    return user_repo.get_by_username(username)


def generate_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ── Auth ──────────────────────────────────────────────────────


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401
        token = auth_header[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
        g.user_id = payload["user_id"]
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
    if get_user_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = user_repo.create(username, generate_password_hash(password))
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    token = generate_token(user["id"], user["username"])
    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    cursor_param = request.args.get("cursor")
    limit_param = request.args.get("limit")

    cursor = None
    if cursor_param is not None:
        try:
            cursor = int(cursor_param)
        except ValueError:
            return jsonify({"error": "cursor must be an integer"}), 400

    limit = DEFAULT_PAGE_LIMIT
    if limit_param is not None:
        try:
            limit = int(limit_param)
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400
    limit = max(1, min(limit, MAX_PAGE_LIMIT))

    rows = task_repo.get_page(g.user_id, cursor, limit)
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = page[-1]["id"] if has_more else None
    total = task_repo.count(g.user_id)

    return jsonify({"data": page, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repo.get_by_id(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    previous = task_repo.get_by_id(task_id, g.user_id)
    task = task_repo.update(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        data.get("status") == "completed"
        and previous is not None
        and previous["status"] != "completed"
    ):
        owner = user_repo.get_by_id(task["owner_id"])
        if owner is not None:
            user_email = f"{owner['username']}@example.com"
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
