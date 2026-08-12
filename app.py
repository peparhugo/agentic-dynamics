"""
Flask Task Management API with JWT authentication.

A single-file Flask app with clean structure: models, auth, routes, error
handling. Uses SQLite for storage, with schema initialized (and migrated)
on startup.

Auth model:
    - Users register with a username/password (password stored as a salted
      hash via werkzeug.security, never in plaintext).
    - Login exchanges valid credentials for a short-lived JWT.
    - All /tasks/* endpoints require "Authorization: Bearer <token>".
    - Tasks are scoped to their owner: users can only see/modify their own
      tasks. A task belonging to another user (or no task at all) returns
      404, so existence of other users' tasks is never leaked.

Rate limiting:
    - Every endpoint (including /auth/*) is rate limited via Flask-Limiter,
      backed by Redis. Authenticated requests are limited per-user (keyed
      off the JWT's ``user_id``); unauthenticated requests fall back to
      per-IP limiting. The limit is a single shared budget across all
      endpoints for a given key (not per-route), so a client can't dodge
      the limit by spreading calls across different endpoints.
    - Exceeding the limit returns 429 with a ``Retry-After`` header.

Pagination:
    - GET /tasks uses cursor-based pagination: ``?cursor=<id>&limit=<n>``.
      The cursor is the ``id`` of the last item of the current page; the
      next page contains tasks with a smaller id (results are ordered
      newest-first). Response shape: ``{data, next_cursor, total}``.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os
import sqlite3

import jwt
from flask import Flask, current_app, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db
from repositories import TaskRepository, UserRepository
from tasks import send_notification_email


JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_SECONDS = 3600

# ── Rate limiting ────────────────────────────────────────────
RATE_LIMIT = "100 per minute"

# ── Pagination ───────────────────────────────────────────────
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Repositories are stateless aside from the ``get_db`` accessor they hold,
# so a single module-level instance per table is reused across requests;
# ``get_db`` itself resolves to the correct per-request connection (via
# Flask's ``g``) each time it's called.
user_repository = UserRepository(get_db)
task_repository = TaskRepository(get_db)


# ── JWT helpers ──────────────────────────────────────────────

def generate_token(secret: str, user_id: int, username: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=TOKEN_EXPIRY_SECONDS),
    }
    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    # PyJWT >= 2 returns a str already; guard against older versions returning bytes.
    return token.decode("utf-8") if isinstance(token, bytes) else token


def decode_token(secret: str, token: str) -> dict:
    return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])


def login_required(view):
    """Require a valid ``Authorization: Bearer <jwt>`` header.

    On success, sets ``g.current_user`` (dict with ``id``/``username``) and
    calls the wrapped view. Otherwise returns a 401 JSON error.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401

        token = auth_header[len("Bearer "):].strip()
        if not token:
            return jsonify({"error": "missing or invalid authorization header"}), 401

        try:
            payload = decode_token(current_app.config["JWT_SECRET"], token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401

        user = user_repository.get_by_id(payload.get("user_id"))
        if user is None:
            return jsonify({"error": "invalid token"}), 401

        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def _rate_limit_key() -> str:
    """Key requests by authenticated user, falling back to IP address.

    Mirrors the token-parsing logic in ``login_required`` but never raises:
    a missing/malformed/expired token just means the request is limited by
    IP instead (the view itself still enforces auth separately). This lets
    a single rate limit apply uniformly to every endpoint, including
    /auth/register and /auth/login, where there's no user yet.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
        if token:
            try:
                payload = decode_token(current_app.config["JWT_SECRET"], token)
            except jwt.InvalidTokenError:
                payload = None
            if payload is not None and payload.get("user_id") is not None:
                return f"user:{payload['user_id']}"
    return f"ip:{get_remote_address()}"


# ── App factory ───────────────────────────────────────────────

def create_app(
    database: str = None,
    jwt_secret: str = None,
    redis_url: str = None,
    rate_limit: str = None,
) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or os.environ.get("DATABASE", "tasks.db")
    app.config["JWT_SECRET"] = jwt_secret or os.environ.get(
        "JWT_SECRET", "dev-insecure-secret-change-me"
    )
    app.config["REDIS_URL"] = redis_url or os.environ.get(
        "REDIS_URL", "redis://localhost:6379/2"
    )
    app.config["RATE_LIMIT"] = rate_limit or os.environ.get("RATE_LIMIT", RATE_LIMIT)

    with app.app_context():
        init_db(app.config["DATABASE"])

    app.teardown_appcontext(close_db)

    # A fresh Limiter (and thus a fresh Redis-backed storage handle) is
    # created per app instance rather than reused as a module-level
    # singleton, so that separate ``create_app()`` calls (e.g. one per
    # test) never share rate-limit counters.
    Limiter(
        key_func=_rate_limit_key,
        app=app,
        application_limits=[app.config["RATE_LIMIT"]],
        storage_uri=app.config["REDIS_URL"],
        headers_enabled=True,
    )

    # ── Auth routes ─────────────────────────────────────────

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}

        username = data.get("username")
        password = data.get("password")
        email = data.get("email")

        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        if email is not None and (not isinstance(email, str) or not email.strip()):
            return jsonify({"error": "email must be a non-empty string"}), 400

        username = username.strip()
        if user_repository.get_by_username(username) is not None:
            return jsonify({"error": "username already exists"}), 409

        # Notifications need *some* address to send to; default to a
        # deterministic placeholder derived from the username when the
        # caller doesn't supply a real one.
        email = email.strip() if isinstance(email, str) else f"{username}@example.com"

        password_hash = generate_password_hash(password)
        try:
            user = user_repository.create(username, password_hash, email)
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409

        return jsonify(user), 201

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}

        username = data.get("username")
        password = data.get("password")

        if (
            not isinstance(username, str)
            or not username.strip()
            or not isinstance(password, str)
            or not password
        ):
            return jsonify({"error": "username and password are required"}), 400

        user = user_repository.get_by_username(username.strip())
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = generate_token(
            app.config["JWT_SECRET"], user["id"], user["username"]
        )
        return jsonify({"token": token, "token_type": "Bearer"})

    # ── Task routes (all protected) ─────────────────────────

    @app.route("/tasks", methods=["POST"])
    @login_required
    def add_task():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = task_repository.create(title.strip(), g.current_user["id"])
        return jsonify(task), 201

    @app.route("/tasks", methods=["GET"])
    @login_required
    def list_tasks():
        cursor_param = request.args.get("cursor")
        limit_param = request.args.get("limit")

        cursor = None
        if cursor_param is not None:
            try:
                cursor = int(cursor_param)
            except ValueError:
                return jsonify({"error": "cursor must be an integer"}), 400

        limit = DEFAULT_PAGE_SIZE
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except ValueError:
                return jsonify({"error": "limit must be an integer"}), 400
            if limit < 1:
                return jsonify({"error": "limit must be a positive integer"}), 400

        limit = min(limit, MAX_PAGE_SIZE)

        page = task_repository.get_page(g.current_user["id"], cursor=cursor, limit=limit)
        next_cursor = page["next_cursor"]
        return jsonify(
            {
                "data": page["data"],
                "next_cursor": str(next_cursor) if next_cursor is not None else None,
                "total": page["total"],
            }
        )

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    @login_required
    def show_task(task_id: int):
        task = task_repository.get_by_id(task_id, g.current_user["id"])
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task)

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    @login_required
    def edit_task(task_id: int):
        existing = task_repository.get_by_id(task_id, g.current_user["id"])
        if existing is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            data = {}

        title = data.get("title")
        status = data.get("status")

        if title is not None and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400
        if status is not None and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400
        if title is None and status is None:
            return jsonify({"error": "title and/or status is required"}), 400

        new_status = status.strip() if status is not None else None
        task = task_repository.update(
            task_id,
            g.current_user["id"],
            title=title.strip() if title is not None else None,
            status=new_status,
        )

        # Fire-and-forget async notification: only when the status is
        # *changing into* 'completed' (not on every no-op re-save of an
        # already-completed task), and never blocking the response.
        if new_status == "completed" and existing["status"] != "completed":
            send_notification_email.delay(g.current_user["email"], task["title"])

        return jsonify(task)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify({"error": "method not allowed"}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(_error):
        return jsonify({"error": "rate limit exceeded"}), 429

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
