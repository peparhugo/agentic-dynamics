"""Flask API for task management.

Storage is flat-file (JSON), not a database — see storage.py.

Endpoints under /tasks require a valid JWT (see /auth/register and
/auth/login). Each user only sees and manages their own tasks.
"""

import os
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

import storage
from repositories import TaskRepository, UserRepository
from tasks import send_notification_email

JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 24

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


def create_app():
    app = Flask(__name__)
    storage.init_storage()

    task_repo = TaskRepository()
    user_repo = UserRepository()

    app.config["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY", "dev-secret-key-change-in-production-32bytes-min"
    )

    def rate_limit_key():
        """Key rate-limit buckets by authenticated user, falling back to IP.

        This runs ahead of the `require_auth` decorator (Flask-Limiter checks
        limits before the view function executes), so it decodes the JWT
        itself rather than relying on `g.user_id`. An invalid/missing token
        still gets rate limited, just by IP instead of by user.
        """
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
            if token:
                try:
                    payload = jwt.decode(
                        token, app.config["JWT_SECRET_KEY"], algorithms=[JWT_ALGORITHM]
                    )
                    return f"user:{payload['sub']}"
                except jwt.InvalidTokenError:
                    pass
        return f"ip:{get_remote_address()}"

    app.config["RATE_LIMIT_PER_MINUTE"] = int(
        os.environ.get("RATE_LIMIT_PER_MINUTE", "100")
    )

    limiter = Limiter(
        app=app,
        key_func=rate_limit_key,
        application_limits=[f"{app.config['RATE_LIMIT_PER_MINUTE']} per minute"],
        storage_uri=os.environ.get(
            "RATELIMIT_STORAGE_URI", "redis://localhost:6379/2"
        ),
        headers_enabled=True,
    )

    def generate_token(user):
        payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS),
        }
        return jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm=JWT_ALGORITHM)

    def require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401

            token = auth_header[len("Bearer "):].strip()
            if not token:
                return jsonify({"error": "Missing or invalid Authorization header"}), 401

            try:
                payload = jwt.decode(
                    token, app.config["JWT_SECRET_KEY"], algorithms=[JWT_ALGORITHM]
                )
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            g.user_id = int(payload["sub"])
            g.username = payload.get("username")
            return f(*args, **kwargs)

        return wrapper

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(_e):
        return jsonify({"error": "Rate limit exceeded"}), 429

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400

        password_hash = generate_password_hash(password)
        user = user_repo.create(username.strip(), password_hash)
        if user is None:
            return jsonify({"error": "username already exists"}), 409

        return jsonify({"id": user["id"], "username": user["username"]}), 201

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400

        user = user_repo.get_by_username(username.strip())
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = generate_token(user)
        return jsonify({"token": token}), 200

    @app.route("/tasks", methods=["POST"])
    @require_auth
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = task_repo.create(title.strip(), g.user_id)
        return jsonify(task), 201

    @app.route("/tasks", methods=["GET"])
    @require_auth
    def list_tasks():
        cursor_param = request.args.get("cursor")
        cursor = None
        if cursor_param is not None:
            try:
                cursor = int(cursor_param)
            except ValueError:
                return jsonify({"error": "cursor must be an integer"}), 400

        limit = DEFAULT_PAGE_LIMIT
        limit_param = request.args.get("limit")
        if limit_param is not None:
            try:
                limit = int(limit_param)
            except ValueError:
                return jsonify({"error": "limit must be an integer"}), 400
            if limit < 1:
                return jsonify({"error": "limit must be a positive integer"}), 400
            limit = min(limit, MAX_PAGE_LIMIT)

        page = task_repo.list_page(g.user_id, cursor=cursor, limit=limit)
        return jsonify(page), 200

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    @require_auth
    def get_task(task_id):
        task = task_repo.get_by_id(task_id)
        if task is None or task.get("owner_id") != g.user_id:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task), 200

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    @require_auth
    def update_task(task_id):
        existing = task_repo.get_by_id(task_id)
        if existing is None or existing.get("owner_id") != g.user_id:
            return jsonify({"error": "Task not found"}), 404

        data = request.get_json(silent=True) or {}
        has_title = "title" in data
        has_status = "status" in data
        if not has_title and not has_status:
            return jsonify({"error": "title or status is required"}), 400

        title = data.get("title")
        if has_title and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400

        status = data.get("status")
        if has_status and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400

        task = task_repo.update(
            task_id,
            title=title.strip() if has_title else None,
            status=status.strip() if has_status else None,
        )

        newly_completed = (
            has_status
            and status.strip() == "completed"
            and existing.get("status") != "completed"
        )
        if newly_completed:
            owner = user_repo.get_by_id(task["owner_id"])
            if owner is not None:
                owner_email = owner.get("email") or f"{owner['username']}@example.com"
                try:
                    send_notification_email.delay(owner_email, task["title"])
                except Exception:
                    app.logger.exception("Failed to enqueue completion notification email")

        return jsonify(task), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
