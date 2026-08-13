"""
Flask API for task management.

Data access goes through the repository layer (see task_repository.py,
user_repository.py, base_repository.py) — route handlers never touch
storage directly. Storage itself is flat-file JSON, not a database. Tasks
are scoped to the authenticated user via JWT bearer tokens (see auth.py).
"""

import os
import secrets

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from auth import create_token, decode_token, hash_password, require_auth, verify_password
from celery_tasks import send_notification_email
from task_repository import TaskRepository
from user_repository import UserRepository

DEFAULT_STORAGE_PATH = os.environ.get("TASKS_STORAGE_PATH", "tasks.json")
DEFAULT_USERS_STORAGE_PATH = os.environ.get("USERS_STORAGE_PATH", "users.json")
DEFAULT_RATE_LIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379/2")
DEFAULT_RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")

PAGINATION_DEFAULT_LIMIT = 20
PAGINATION_MAX_LIMIT = 100


def create_app(storage_path: str = DEFAULT_STORAGE_PATH,
                users_storage_path: str = DEFAULT_USERS_STORAGE_PATH,
                rate_limit_storage_uri: str = DEFAULT_RATE_LIMIT_STORAGE_URI,
                rate_limit: str = DEFAULT_RATE_LIMIT) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    app.task_repository = TaskRepository(storage_path)
    app.user_repository = UserRepository(users_storage_path)
    auth_required = require_auth(app)

    def rate_limit_key() -> str:
        # Authenticated requests are limited per user; requests without a
        # valid token (e.g. login/register) fall back to per-IP limiting.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token, app.config["SECRET_KEY"])
            if payload is not None:
                return f"user:{payload['sub']}"
        return get_remote_address()

    app.limiter = Limiter(
        app=app,
        key_func=rate_limit_key,
        storage_uri=rate_limit_storage_uri,
        headers_enabled=True,
    )
    # A single shared bucket per key (user, or IP when unauthenticated) so
    # the limit is "N requests per minute" across the whole API, not N per
    # individual endpoint.
    limited = app.limiter.shared_limit(rate_limit, scope="global")

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(_e):
        return jsonify({"error": "rate limit exceeded"}), 429

    @app.post("/auth/register")
    @limited
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        if email is not None and (not isinstance(email, str) or "@" not in email):
            return jsonify({"error": "email must be a valid email address"}), 400
        username = username.strip()
        if app.user_repository.get_by_username(username) is not None:
            return jsonify({"error": "username already taken"}), 409
        email = email.strip() if email else f"{username}@example.com"
        user = app.user_repository.create(username, hash_password(password), email)
        return jsonify({"id": user["id"], "username": user["username"], "email": user["email"]}), 201

    @app.post("/auth/login")
    @limited
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return jsonify({"error": "username and password are required"}), 400
        user = app.user_repository.get_by_username(username.strip())
        if user is None or not verify_password(password, user["password_hash"]):
            return jsonify({"error": "invalid username or password"}), 401
        token = create_token(user, app.config["SECRET_KEY"])
        return jsonify({"token": token}), 200

    @app.post("/tasks")
    @limited
    @auth_required
    def create_task(user):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = app.task_repository.create(title.strip(), owner_id=user["id"])
        return jsonify(task), 201

    @app.get("/tasks")
    @limited
    @auth_required
    def list_tasks(user):
        cursor_param = request.args.get("cursor")
        limit_param = request.args.get("limit")

        cursor = None
        if cursor_param is not None:
            try:
                cursor = int(cursor_param)
            except ValueError:
                return jsonify({"error": "cursor must be an integer"}), 400

        limit = PAGINATION_DEFAULT_LIMIT
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except ValueError:
                return jsonify({"error": "limit must be an integer"}), 400
        if limit < 1 or limit > PAGINATION_MAX_LIMIT:
            return jsonify({"error": f"limit must be between 1 and {PAGINATION_MAX_LIMIT}"}), 400

        page = app.task_repository.list_page(owner_id=user["id"], cursor=cursor, limit=limit)
        if page is None:
            return jsonify({"error": "invalid cursor"}), 400
        return jsonify(page), 200

    @app.get("/tasks/<int:task_id>")
    @limited
    @auth_required
    def get_task(user, task_id):
        task = app.task_repository.get(task_id, owner_id=user["id"])
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task), 200

    @app.put("/tasks/<int:task_id>")
    @limited
    @auth_required
    def update_task(user, task_id):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        status = data.get("status")

        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400
        if title is not None and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400
        if status is not None and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400

        previous_task = app.task_repository.get(task_id, owner_id=user["id"])
        task = app.task_repository.update(
            task_id,
            owner_id=user["id"],
            title=title.strip() if title is not None else None,
            status=status.strip() if status is not None else None,
        )
        if task is None:
            return jsonify({"error": "task not found"}), 404

        newly_completed = (
            status is not None
            and task["status"] == "completed"
            and (previous_task is None or previous_task["status"] != "completed")
        )
        if newly_completed:
            try:
                send_notification_email.delay(user["email"], task["title"])
            except Exception:
                app.logger.exception(
                    "failed to enqueue completion notification for task %s", task_id
                )

        return jsonify(task), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
