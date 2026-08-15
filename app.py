"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from functools import wraps

import jwt
from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import os

from celery_app import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# 'completed' is an alias status alongside the original 'pending'/'done' pair.
# It exists so a status update can trigger the completion notification email
# without altering the meaning or behavior of the pre-existing 'done' status.
VALID_STATUSES = {"pending", "done", "completed"}
TOKEN_TTL = timedelta(hours=24)

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


# ── Rate limiting ────────────────────────────────────────────────

def rate_limit_key() -> str:
    """Key by authenticated user id when a valid token is present, else by IP.

    This lets the same 100/minute budget apply per-user on authenticated
    routes while still rate limiting anonymous callers of /auth/register
    and /auth/login (which have no user id yet) by their remote address.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            return f"user:{payload['user_id']}"
        except jwt.InvalidTokenError:
            pass
    return get_remote_address()


RATE_LIMIT = "100 per minute"

# key_prefix namespaces this app's rate-limit keys in the (possibly shared)
# Redis instance so its counters can't collide with other apps/deployments.
RATE_LIMIT_KEY_PREFIX = "taskapi_0799a58de870_ratelimit"

# application_limits (rather than default_limits) is used because it shares
# a single bucket per key across every route (scope="global"); default_limits
# would instead give each endpoint its own independent 100/minute bucket.
limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/0"),
    key_prefix=RATE_LIMIT_KEY_PREFIX,
    application_limits=[RATE_LIMIT],
    headers_enabled=True,
)


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
            "  password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        _migrate_add_owner_id(conn)


def _migrate_add_owner_id(conn):
    """Add tasks.owner_id to databases created before auth existed.

    CREATE TABLE IF NOT EXISTS is a no-op on an already-existing tasks
    table, so pre-auth databases need this column added explicitly.
    Existing tasks keep owner_id = NULL rather than being deleted.
    """
    cols = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "owner_id" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


# ── Repositories ──────────────────────────────────────────────

# get_db is passed in (rather than imported by the repositories module) so
# that repositories always resolve the current DATABASE global at call time,
# even when it's reassigned after import (as the test suite does).
user_repo = UserRepository(get_db)
task_repo = TaskRepository(get_db)


# ── Models ────────────────────────────────────────────────────

def create_user(username: str, password: str) -> dict | None:
    password_hash = generate_password_hash(password)
    return user_repo.create(username, password_hash)


def get_user_by_username(username: str) -> dict | None:
    return user_repo.find_by_username(username)


def get_user_by_id(user_id: int) -> dict | None:
    return user_repo.find_by_id(user_id)


def create_task(title: str, owner_id: int) -> dict:
    return task_repo.create(title, owner_id)


def get_tasks_page(owner_id: int, cursor: int | None, limit: int):
    return task_repo.find_page_by_owner(owner_id, cursor=cursor, limit=limit)


def get_task(task_id: int) -> dict | None:
    return task_repo.find_by_id(task_id)


def update_task(task_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    return task_repo.update(task_id, title=title, status=status)


# ── Auth helpers ─────────────────────────────────────────────────

def generate_token(user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.utcnow() + TOKEN_TTL,
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
        g.user_id = payload["user_id"]
        return f(*args, **kwargs)

    return decorated


# ── Auth routes ────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = create_user(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
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
    return jsonify({"token": token})


# ── Task routes ────────────────────────────────────────────────

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
        if limit < 1:
            return jsonify({"error": "limit must be a positive integer"}), 400
    limit = min(limit, MAX_PAGE_LIMIT)

    data, next_cursor, total = get_tasks_page(g.user_id, cursor=cursor, limit=limit)
    return jsonify({
        "data": data,
        "next_cursor": str(next_cursor) if next_cursor is not None else None,
        "total": total,
    })


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id)
    if task is None or task["owner_id"] != g.user_id:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        return jsonify({"error": f"invalid status: {status!r}"}), 422
    existing = get_task(task_id)
    if existing is None or existing["owner_id"] != g.user_id:
        return jsonify({"error": "task not found"}), 404
    task = update_task(
        task_id,
        title=data.get("title"),
        status=status,
    )
    if status == "completed" and existing["status"] != "completed":
        owner = get_user_by_id(task["owner_id"])
        if owner is not None:
            send_notification_email.delay(owner["username"], task["title"])
    return jsonify(task)


# ── Error handlers ───────────────────────────────────────────────

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(405)
def handle_405(e):
    return jsonify({"error": "method not allowed"}), 405


@app.errorhandler(429)
def handle_429(e):
    # flask-limiter injects the Retry-After header onto this response via
    # an after_request hook, using the limit that was breached.
    return jsonify({"error": "rate limit exceeded"}), 429


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
