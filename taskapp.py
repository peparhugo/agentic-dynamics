"""Flask API for task management, backed by SQLite, with JWT authentication."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash

from notifications import send_notification_email
from repositories import UserRepository, TaskRepository, init_db

TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))

DEFAULT_TASKS_PAGE_LIMIT = 20
MAX_TASKS_PAGE_LIMIT = 100


def create_app(
    database: str = "tasks.db",
    rate_limit_storage_uri: str | None = None,
    rate_limit: str | None = None,
) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-secret-key-change-me-in-production-please"
    )
    init_db(database)

    user_repo = UserRepository(database)
    task_repo = TaskRepository(database)

    def rate_limit_key() -> str:
        """Key rate limits by authenticated user id, falling back to IP
        for unauthenticated requests (e.g. login/register)."""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
            try:
                payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
                return f"user:{payload.get('sub')}"
            except jwt.InvalidTokenError:
                pass
        return f"ip:{get_remote_address()}"

    storage_uri = rate_limit_storage_uri or os.environ.get(
        "RATELIMIT_STORAGE_URI", "redis://localhost:6379/2"
    )
    limit = rate_limit or os.environ.get("RATE_LIMIT", "100 per minute")
    limiter = Limiter(
        rate_limit_key,
        app=app,
        application_limits=[limit],
        storage_uri=storage_uri,
        headers_enabled=True,
        # Unique per app instance so separate app instances (e.g. in tests)
        # never share rate-limit counters even when using the same storage.
        key_prefix=f"taskapp:{uuid.uuid4().hex}",
    )

    @app.errorhandler(429)
    def rate_limit_exceeded(_e):
        return jsonify({"error": "rate limit exceeded"}), 429

    def make_token(user_id: int, username: str) -> str:
        payload = {
            "sub": str(user_id),
            "username": username,
            "exp": datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS),
        }
        return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

    def require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing or invalid authorization header"}), 401
            token = auth_header[len("Bearer "):].strip()
            try:
                payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "invalid token"}), 401

            try:
                user_id = int(payload.get("sub"))
            except (TypeError, ValueError):
                return jsonify({"error": "invalid token"}), 401

            user = user_repo.get_by_id(user_id)
            if user is None:
                return jsonify({"error": "invalid token"}), 401

            return f(user, *args, **kwargs)

        return wrapper

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "method not allowed"}), 405

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        if email is not None and not isinstance(email, str):
            return jsonify({"error": "email must be a string"}), 400
        username = username.strip()
        email = email.strip() if isinstance(email, str) and email.strip() else f"{username}@example.com"

        existing = user_repo.get_by_username(username)
        if existing is not None:
            return jsonify({"error": "username already taken"}), 409

        password_hash = generate_password_hash(password)
        user_id = user_repo.create(username, password_hash, email)
        return jsonify({"id": user_id, "username": username, "email": email}), 201

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        username = username.strip()

        user = user_repo.get_by_username(username)

        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = make_token(user["id"], user["username"])
        return jsonify({"token": token})

    @app.route("/tasks", methods=["POST"])
    @require_auth
    def create_task(user):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        now = datetime.now(timezone.utc).isoformat()
        row = task_repo.create(title.strip(), "pending", now, user["id"])
        return jsonify(dict(row)), 201

    @app.route("/tasks", methods=["GET"])
    @require_auth
    def list_tasks(user):
        cursor_param = request.args.get("cursor")
        cursor = None
        if cursor_param is not None:
            try:
                cursor = int(cursor_param)
            except ValueError:
                return jsonify({"error": "cursor must be an integer"}), 400

        limit_param = request.args.get("limit")
        limit = DEFAULT_TASKS_PAGE_LIMIT
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except ValueError:
                return jsonify({"error": "limit must be an integer"}), 400
            if limit < 1:
                return jsonify({"error": "limit must be a positive integer"}), 400
        limit = min(limit, MAX_TASKS_PAGE_LIMIT)

        rows = task_repo.list_page_for_owner(user["id"], cursor, limit)
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = str(page_rows[-1]["id"]) if has_more and page_rows else None
        total = task_repo.count_for_owner(user["id"])

        return jsonify({
            "data": [dict(r) for r in page_rows],
            "next_cursor": next_cursor,
            "total": total,
        })

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    @require_auth
    def get_task(user, task_id):
        row = task_repo.get_for_owner(task_id, user["id"])
        if row is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(dict(row))

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    @require_auth
    def update_task(user, task_id):
        row = task_repo.get_for_owner(task_id, user["id"])
        if row is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({"error": "no fields to update"}), 400

        title = row["title"]
        status = row["status"]
        previous_status = row["status"]

        if "title" in data:
            new_title = data.get("title")
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            title = new_title.strip()

        if "status" in data:
            new_status = data.get("status")
            if not isinstance(new_status, str) or not new_status.strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            status = new_status.strip()

        row = task_repo.update(task_id, title, status)

        just_completed = status == "completed" and previous_status != "completed"
        if just_completed:
            try:
                send_notification_email.delay(user["email"], row["title"])
            except Exception:
                app.logger.exception("failed to enqueue completion notification email")

        return jsonify(dict(row))

    return app


if __name__ == "__main__":
    application = create_app(os.environ.get("DATABASE", "tasks.db"))
    application.run(debug=True)
