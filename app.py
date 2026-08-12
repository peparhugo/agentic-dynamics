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
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os
import sqlite3

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db
from repositories import TaskRepository, UserRepository
from tasks import send_notification_email


JWT_ALGORITHM = "HS256"
TOKEN_EXPIRY_SECONDS = 3600

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


# ── App factory ───────────────────────────────────────────────

def create_app(database: str = None, jwt_secret: str = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or os.environ.get("DATABASE", "tasks.db")
    app.config["JWT_SECRET"] = jwt_secret or os.environ.get(
        "JWT_SECRET", "dev-insecure-secret-change-me"
    )

    with app.app_context():
        init_db(app.config["DATABASE"])

    app.teardown_appcontext(close_db)

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
        return jsonify(task_repository.get_all(g.current_user["id"]))

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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
