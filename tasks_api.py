"""Flask API for task management, backed by SQLite.

SQLite's INTEGER PRIMARY KEY without AUTOINCREMENT can still reuse ids after
deletes, so task ids are assigned manually from a counter persisted in a
dedicated `counters` table rather than relying on SQLite's rowid behavior.

Endpoints under /tasks require a JWT bearer token obtained via /auth/login.
Each task is scoped to the user that created it (Task.owner_id).
"""

import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email
from task_repository import TaskRepository
from user_repository import UserRepository

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")

JWT_ALGORITHM = "HS256"
JWT_EXP_SECONDS = 3600
MIN_PASSWORD_LENGTH = 6

DEFAULT_RATE_LIMIT = "100 per minute"
DEFAULT_RATELIMIT_STORAGE_URI = "redis://localhost:6379/2"

DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counters (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
        conn.execute("INSERT OR IGNORE INTO counters (name, value) VALUES ('task_id', 1)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # Migration: databases created before auth existed won't have an
        # owner_id column on tasks. Add it in place so pre-existing rows are
        # preserved (they end up with owner_id = NULL, i.e. unowned legacy
        # tasks that no user will see until reassigned).
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in existing_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")

        # Migration: databases created before the email notification feature
        # won't have an email column on users. Existing rows get NULL, i.e.
        # legacy users who won't receive notifications until they set one.
        existing_user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

        conn.commit()
    finally:
        conn.close()


def _task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


def _user_to_dict(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


def _generate_token(user_id, secret_key):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(seconds=JWT_EXP_SECONDS),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def create_app(db_path=None, secret_key=None, storage_uri=None, rate_limit=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or DEFAULT_DB_PATH
    app.config["SECRET_KEY"] = secret_key or os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    init_db(app.config["DB_PATH"])

    def get_db():
        db = getattr(g, "_database", None)
        if db is None:
            db = g._database = sqlite3.connect(app.config["DB_PATH"])
            db.row_factory = sqlite3.Row
        return db

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("_database", None)
        if db is not None:
            db.close()

    def rate_limit_key():
        # Rate limiting runs before the view (and before require_auth), so the
        # JWT is decoded independently here rather than reusing g.current_user.
        # A missing/invalid token falls back to limiting by IP, which still
        # covers unauthenticated endpoints like /auth/login and /auth/register.
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
            if token:
                try:
                    payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[JWT_ALGORITHM])
                    return f"user:{payload.get('sub')}"
                except jwt.PyJWTError:
                    pass
        return f"ip:{get_remote_address()}"

    app.config["RATELIMIT_STORAGE_URI"] = (
        storage_uri or os.environ.get("RATELIMIT_STORAGE_URI") or DEFAULT_RATELIMIT_STORAGE_URI
    )
    Limiter(
        key_func=rate_limit_key,
        app=app,
        storage_uri=app.config["RATELIMIT_STORAGE_URI"],
        # application_limits (rather than default_limits) share a single
        # counter per key across every route, so a user's 100/minute budget
        # is a total across all endpoints rather than 100 per endpoint.
        application_limits=[rate_limit or DEFAULT_RATE_LIMIT],
        headers_enabled=True,
    )

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def handle_429(e):
        return jsonify({"error": "rate limit exceeded"}), 429

    def require_auth(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing or invalid authorization header"}), 401

            token = auth_header[len("Bearer "):].strip()
            if not token:
                return jsonify({"error": "missing or invalid authorization header"}), 401

            try:
                payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[JWT_ALGORITHM])
            except jwt.PyJWTError:
                return jsonify({"error": "invalid or expired token"}), 401

            user_repo = UserRepository(get_db())
            user = user_repo.get_by_id(payload.get("sub"))
            if user is None:
                return jsonify({"error": "invalid or expired token"}), 401

            g.current_user = user
            return view(*args, **kwargs)

        return wrapped

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")

        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            return jsonify(
                {"error": f"password is required and must be at least {MIN_PASSWORD_LENGTH} characters"}
            ), 400
        if email is not None and (not isinstance(email, str) or not email.strip()):
            return jsonify({"error": "email must be a non-empty string"}), 400

        username = username.strip()
        email = email.strip() if email is not None else f"{username}@example.com"
        user_repo = UserRepository(get_db())
        existing = user_repo.get_by_username(username)
        if existing is not None:
            return jsonify({"error": "username already taken"}), 409

        password_hash = generate_password_hash(password)
        created_at = datetime.now(timezone.utc).isoformat()
        row = user_repo.create(username, password_hash, email, created_at)
        return jsonify(_user_to_dict(row)), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return jsonify({"error": "username and password are required"}), 400

        user_repo = UserRepository(get_db())
        row = user_repo.get_by_username(username.strip())
        if row is None or not check_password_hash(row["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = _generate_token(row["id"], app.config["SECRET_KEY"])
        return jsonify({"token": token}), 200

    @app.post("/tasks")
    @require_auth
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        task_repo = TaskRepository(get_db())
        created_at = datetime.now(timezone.utc).isoformat()
        row = task_repo.create(title, "pending", created_at, g.current_user["id"])
        return jsonify(_task_to_dict(row)), 201

    @app.get("/tasks")
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

        task_repo = TaskRepository(get_db())
        rows = task_repo.list_by_owner_page(g.current_user["id"], cursor, limit + 1)
        has_more = len(rows) > limit
        rows = rows[:limit]
        total = task_repo.count_by_owner(g.current_user["id"])

        return jsonify(
            {
                "data": [_task_to_dict(r) for r in rows],
                "next_cursor": str(rows[-1]["id"]) if has_more else None,
                "total": total,
            }
        ), 200

    @app.get("/tasks/<int:task_id>")
    @require_auth
    def get_task(task_id):
        task_repo = TaskRepository(get_db())
        row = task_repo.get_by_id_and_owner(task_id, g.current_user["id"])
        if row is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404
        return jsonify(_task_to_dict(row)), 200

    @app.put("/tasks/<int:task_id>")
    @require_auth
    def update_task(task_id):
        task_repo = TaskRepository(get_db())
        row = task_repo.get_by_id_and_owner(task_id, g.current_user["id"])
        if row is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404

        data = request.get_json(silent=True) or {}
        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400

        title = row["title"]
        previous_status = row["status"]
        status = previous_status

        if "title" in data:
            new_title = data["title"]
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            title = new_title

        if "status" in data:
            new_status = data["status"]
            if not isinstance(new_status, str) or not new_status.strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            status = new_status

        row = task_repo.update(task_id, g.current_user["id"], title, status)

        if previous_status != "completed" and status == "completed":
            owner_email = g.current_user["email"]
            if owner_email:
                try:
                    send_notification_email.delay(owner_email, row["title"])
                except Exception:
                    app.logger.exception("Failed to enqueue completion notification email")

        return jsonify(_task_to_dict(row)), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
