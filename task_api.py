"""
Flask API for task management, backed by SQLite, protected by JWT auth.

Models:
    User: id (int, auto), username (str, unique), password_hash (str)
    Task: id (int, auto), title (str), status (str, default 'pending'),
          created_at (datetime), owner_id (int, FK -> users.id)

Auth endpoints:
    POST   /auth/register  create a user      (JSON: {username, password})
    POST   /auth/login     obtain a JWT token (JSON: {username, password})

Task endpoints (require "Authorization: Bearer <token>"):
    POST   /tasks       create a task for the current user
    GET    /tasks       list the current user's tasks, ordered by created_at desc
    GET    /tasks/<id>  get a single task owned by the current user
    PUT    /tasks/<id>  update task title and/or status (must be owned by the current user)

Notifications:
    When PUT /tasks/<id> transitions a task's status to 'completed', a
    send_notification_email Celery task is queued asynchronously (via Redis)
    to notify the task owner; it never blocks or fails the API response.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from celery_app import send_notification_email
from repositories import TaskRepository, UserRepository

logger = logging.getLogger(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXP_SECONDS = int(os.environ.get("JWT_EXP_SECONDS", "3600"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    email TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    owner_id INTEGER REFERENCES users(id)
);
"""

VALID_STATUSES = {"pending", "in_progress", "completed"}
MIN_PASSWORD_LENGTH = 8


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.get("db_path", DATABASE))
        g.db.row_factory = sqlite3.Row
    return g.db


def _migrate_add_owner_id(conn):
    """Add tasks.owner_id to databases created before auth existed.

    Pre-existing tasks end up with owner_id = NULL (unowned) rather than
    being deleted, so no data is lost; they simply won't appear in any
    user's task list until reassigned.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        conn.commit()


def _migrate_add_email(conn):
    """Add users.email to databases created before notifications existed."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


def init_db(database_path):
    conn = sqlite3.connect(database_path)
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate_add_owner_id(conn)
    _migrate_add_email(conn)
    conn.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


def generate_token(user_id, username):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + timedelta(seconds=JWT_EXP_SECONDS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token):
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify(error="Missing or invalid authorization header"), 401
        token = auth_header[len("Bearer "):].strip()
        if not token:
            return jsonify(error="Missing or invalid authorization header"), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify(error="Token has expired"), 401
        except jwt.InvalidTokenError:
            return jsonify(error="Invalid token"), 401
        g.current_user_id = payload["sub"]
        return view(*args, **kwargs)

    return wrapped


def create_app(database_path=None):
    app = Flask(__name__)
    db_path = database_path or DATABASE
    app.config["DATABASE"] = db_path
    init_db(db_path)

    @app.before_request
    def _set_db_path():
        g.db_path = app.config["DATABASE"]

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def not_found(e):
        return jsonify(error="Not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify(error="Method not allowed"), 405

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error="Bad request"), 400

    # ── Auth ─────────────────────────────────────────────────────

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Request body must be a JSON object"), 400

        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip():
            return jsonify(error="username is required"), 400
        if not isinstance(password, str) or not password:
            return jsonify(error="password is required"), 400
        if len(password) < MIN_PASSWORD_LENGTH:
            return jsonify(error=f"password must be at least {MIN_PASSWORD_LENGTH} characters"), 400

        username = username.strip()
        user_repo = UserRepository(get_db())
        existing = user_repo.get_by_username(username)
        if existing is not None:
            return jsonify(error="username already taken"), 409

        email = data.get("email")
        if not isinstance(email, str) or not email.strip():
            email = f"{username}@example.com"
        else:
            email = email.strip()

        password_hash = generate_password_hash(password)
        user_id = user_repo.create_user(username, password_hash, email)
        return jsonify(id=user_id, username=username), 201

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Request body must be a JSON object"), 400

        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify(error="username and password are required"), 400

        user_repo = UserRepository(get_db())
        row = user_repo.get_by_username(username.strip())
        if row is None or not check_password_hash(row["password_hash"], password):
            return jsonify(error="Invalid username or password"), 401

        token = generate_token(row["id"], row["username"])
        return jsonify(token=token, username=row["username"]), 200

    # ── Tasks ────────────────────────────────────────────────────

    @app.route("/tasks", methods=["POST"])
    @require_auth
    def create_task():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Request body must be a JSON object"), 400
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify(error="title is required"), 400

        status = data.get("status", "pending")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            return jsonify(error=f"status must be one of {sorted(VALID_STATUSES)}"), 400

        created_at = datetime.now(timezone.utc).isoformat()
        task_repo = TaskRepository(get_db())
        task_id = task_repo.create_task(title.strip(), status, created_at, g.current_user_id)
        row = task_repo.get_by_id(task_id)
        return jsonify(task_to_dict(row)), 201

    @app.route("/tasks", methods=["GET"])
    @require_auth
    def list_tasks():
        task_repo = TaskRepository(get_db())
        rows = task_repo.list_by_owner(g.current_user_id)
        return jsonify([task_to_dict(row) for row in rows]), 200

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    @require_auth
    def get_task(task_id):
        task_repo = TaskRepository(get_db())
        row = task_repo.get_by_id_and_owner(task_id, g.current_user_id)
        if row is None:
            return jsonify(error="Task not found"), 404
        return jsonify(task_to_dict(row)), 200

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    @require_auth
    def update_task(task_id):
        task_repo = TaskRepository(get_db())
        row = task_repo.get_by_id_and_owner(task_id, g.current_user_id)
        if row is None:
            return jsonify(error="Task not found"), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Request body must be a JSON object"), 400

        title = row["title"]
        status = row["status"]

        if "title" in data:
            new_title = data["title"]
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify(error="title must be a non-empty string"), 400
            title = new_title.strip()

        if "status" in data:
            new_status = data["status"]
            if not isinstance(new_status, str) or new_status not in VALID_STATUSES:
                return jsonify(error=f"status must be one of {sorted(VALID_STATUSES)}"), 400
            status = new_status

        status_became_completed = status == "completed" and row["status"] != "completed"

        task_repo.update_task(task_id, title, status)
        updated = task_repo.get_by_id(task_id)

        if status_became_completed:
            user_repo = UserRepository(get_db())
            owner = user_repo.get_by_id(g.current_user_id)
            if owner is not None:
                owner_email = owner["email"] or owner["username"]
                try:
                    send_notification_email.delay(owner_email, updated["title"])
                except Exception:
                    logger.exception("Failed to queue completion notification for task %s", task_id)

        return jsonify(task_to_dict(updated)), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
