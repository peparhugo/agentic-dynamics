"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.

Session 2: Added JWT authentication.
 - Users register/login and receive a JWT.
 - All /tasks/* endpoints require a valid JWT (Authorization: Bearer <token>).
 - Tasks are scoped to their owner (Task.owner_id).

Session 3: Added async email notifications.
 - When a task's status changes to 'completed' via PUT /tasks/{id}, a
   Celery task (send_notification_email) is queued to notify the owner.
   The queuing call (`.delay(...)`) is non-blocking, so the API response
   is not delayed by sending the notification.

Session 4: Added rate limiting and cursor-based pagination.
 - Every endpoint (including /auth/*) is rate limited to 100 requests per
   minute per identity. Authenticated requests are keyed by user id (so
   each user gets their own 100/min budget); unauthenticated requests
   (e.g. /auth/login before a token exists) fall back to the client's IP.
   Exceeding the limit returns 429 with a ``Retry-After`` header.
 - GET /tasks now returns a cursor-paginated page instead of the full
   list: ``{"data": [...], "next_cursor": str|null, "total": int}``.
"""

from functools import wraps

from flask import Flask, request, jsonify, g
from datetime import timedelta, timezone, datetime
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

# Secret used to sign JWTs. In production this MUST come from a secure,
# externally-managed secret (env var / secrets manager), never hardcoded.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = int(os.environ.get("JWT_EXP_MINUTES", "60"))

# ── Pagination defaults ───────────────────────────────────────
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100

# ── Rate limiting ─────────────────────────────────────────────
#
# Storage backend is Redis (as required for a real multi-process/worker
# deployment; Flask-Limiter's default in-memory storage is per-process and
# wouldn't correctly enforce a shared limit). The URI is overridable via
# env var so tests/CI can point at a different Redis db than dev/prod.
RATELIMIT_STORAGE_URI = os.environ.get(
    "RATELIMIT_STORAGE_URI", "redis://localhost:6379/2"
)
RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist, and migrate older schemas in place.

    Migration: existing ``tasks`` tables created before authentication was
    added won't have an ``owner_id`` column. We add it (nullable) so existing
    rows are preserved. Pre-existing tasks simply have no owner until claimed
    or reassigned by an admin/data-fix; they won't show up for any user's
    "my tasks" list (get_tasks always filters by owner_id), which is the safe
    default rather than leaking old data across accounts.
    """
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

        # Migration step for pre-existing databases created before owner_id
        # existed: add the column if it's missing so we don't break old data.
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")

        # Migration step for pre-existing databases created before the
        # notification system needed an email address on file for users.
        user_columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

        conn.commit()


# ── Repositories ──────────────────────────────────────────────
#
# All SQL lives in the repository classes. ``get_db`` is injected as a
# factory rather than baked in, so repositories always pick up the
# *current* value of ``DATABASE`` (e.g. when tests monkeypatch it) instead
# of a stale connection/path captured at import time.

user_repository = UserRepository(get_db)
task_repository = TaskRepository(get_db)


# ── User model ────────────────────────────────────────────────
#
# Thin wrappers around UserRepository, kept as module-level functions so
# callers (routes, tests) have a stable, storage-agnostic API. No SQL
# appears here or in the routes below — it all lives in UserRepository.

def create_user(username: str, password: str, email: str | None = None) -> dict:
    password_hash = generate_password_hash(password)
    # Fall back to a synthesized address when none is provided so every
    # user has *some* email on file for notifications (registration keeps
    # working without callers needing to change).
    email = email or f"{username}@example.com"
    return user_repository.create(
        username=username, password_hash=password_hash, email=email
    )


def get_user_by_username(username: str) -> dict | None:
    return user_repository.get_by_username(username)


def get_user_by_id(user_id: int) -> dict | None:
    return user_repository.get_by_id(user_id)


# ── JWT helpers ───────────────────────────────────────────────

def generate_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError subclasses on invalid/expired tokens."""
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])


# ── Rate limit identity ───────────────────────────────────────
#
# Each *authenticated user* gets their own 100 req/min budget, so one
# user's activity never eats into another's. Requests that don't carry a
# valid token (most notably /auth/register and /auth/login, which run
# before a token exists) fall back to the client's IP address so those
# endpoints are still protected.

def rate_limit_key() -> str:
    auth_header = request.headers.get("Authorization", "")
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        try:
            payload = decode_token(parts[1])
        except jwt.PyJWTError:
            payload = None
        if payload is not None and payload.get("sub") is not None:
            return f"user:{payload['sub']}"
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    storage_uri=RATELIMIT_STORAGE_URI,
    # ``application_limits`` (rather than ``default_limits``) gives each
    # identity ONE shared 100/min budget across every endpoint. With
    # ``default_limits`` each route would get its own independent counter,
    # which would let a user make 100 requests to *each* endpoint per
    # minute instead of 100 total.
    application_limits=[RATE_LIMIT],
    headers_enabled=True,
)


@app.errorhandler(429)
def ratelimit_exceeded(e):
    return (
        jsonify({"error": "rate limit exceeded", "message": str(e.description)}),
        429,
    )


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()

        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "missing or invalid authorization header"}), 401

        token = parts[1]
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.PyJWTError:
            return jsonify({"error": "invalid token"}), 401

        user = get_user_by_id(payload.get("sub"))
        if user is None:
            return jsonify({"error": "invalid token"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


# ── Task model ────────────────────────────────────────────────
#
# Thin wrappers around TaskRepository. No SQL here or in the routes below
# — it all lives in TaskRepository.

def create_task(title: str, owner_id: int) -> dict:
    return task_repository.create(title=title, owner_id=owner_id)


def get_tasks_page(owner_id: int, cursor: int | None, limit: int) -> dict:
    """Return one cursor-paginated page of tasks for ``owner_id``.

    ``cursor`` is the id of the last item the caller has already seen (or
    None for the first page). Pages are ordered by id descending, which is
    equivalent to insertion/created_at order since ids are assigned by an
    autoincrementing sequence.
    """
    rows = task_repository.get_page_for_owner(owner_id, cursor=cursor, limit=limit)

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = str(items[-1]["id"]) if has_more and items else None
    total = task_repository.count_for_owner(owner_id)

    return {"data": items, "next_cursor": next_cursor, "total": total}


def get_task(task_id: int, owner_id: int) -> dict | None:
    return task_repository.get_by_id_for_owner(task_id, owner_id)


def update_task(
    task_id: int,
    owner_id: int,
    title: str | None = None,
    status: str | None = None,
) -> dict | None:
    return task_repository.update(task_id, owner_id, title=title, status=status)


# ── Auth routes ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip() or None

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if get_user_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409

    user = create_user(username, password, email)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401

    token = generate_token(user["id"])
    return jsonify({"token": token}), 200


# ── Task routes ───────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    cursor_param = request.args.get("cursor")
    limit_param = request.args.get("limit")

    cursor = None
    if cursor_param is not None and cursor_param != "":
        try:
            cursor = int(cursor_param)
        except ValueError:
            return jsonify({"error": "cursor must be an integer id"}), 400

    limit = DEFAULT_PAGE_LIMIT
    if limit_param is not None and limit_param != "":
        try:
            limit = int(limit_param)
        except ValueError:
            return jsonify({"error": "limit must be an integer"}), 400

    if limit < 1:
        return jsonify({"error": "limit must be at least 1"}), 400
    limit = min(limit, MAX_PAGE_LIMIT)

    page = get_tasks_page(g.current_user["id"], cursor=cursor, limit=limit)
    return jsonify(page)


@app.route("/tasks", methods=["POST"])
@token_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, g.current_user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def show_task(task_id: int):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}

    existing = get_task(task_id, g.current_user["id"])
    if existing is None:
        return jsonify({"error": "task not found"}), 404

    new_status = data.get("status")
    task = update_task(
        task_id,
        g.current_user["id"],
        title=data.get("title"),
        status=new_status,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404

    # Fire an async notification email when the status transitions *into*
    # 'completed'. Using .delay() queues the task on the broker and
    # returns immediately, so the API response is not blocked waiting for
    # the (mocked) email to be sent.
    if new_status == "completed" and existing["status"] != "completed":
        owner_email = g.current_user.get("email") or f"{g.current_user['username']}@example.com"
        send_notification_email.delay(owner_email, task["title"])

    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
