"""Flask API for task management, backed by SQLite, protected by JWT auth."""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import jwt

from celery_app import send_notification_email
from repositories import TaskRepository, UserRepository

DATABASE = os.environ.get("TASKS_DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = int(os.environ.get("JWT_TTL_SECONDS", "3600"))


def create_app(database=None):
    app = Flask(__name__)
    app.config["DATABASE"] = database or DATABASE
    app.config["JWT_SECRET"] = JWT_SECRET

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def get_user_repo():
        return UserRepository(get_db())

    def get_task_repo():
        return TaskRepository(get_db())

    def init_db():
        conn = sqlite3.connect(app.config["DATABASE"])
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER
            )
            """
        )
        # Migration: older databases may already have a tasks table
        # without owner_id. Add the column if it's missing so existing
        # data survives the upgrade instead of breaking on startup.
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(tasks)")
        }
        if "owner_id" not in existing_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()
        conn.close()

    app.init_db = init_db
    init_db()

    def create_token(user_id):
        payload = {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(seconds=JWT_TTL_SECONDS),
        }
        return jwt.encode(payload, app.config["JWT_SECRET"], algorithm=JWT_ALGORITHM)

    def get_user_from_token(token):
        try:
            payload = jwt.decode(
                token, app.config["JWT_SECRET"], algorithms=[JWT_ALGORITHM]
            )
        except jwt.PyJWTError:
            return None
        return get_user_repo().get_by_id(payload.get("sub"))

    def require_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return jsonify({"error": "missing or invalid authorization header"}), 401
            token = auth.split(" ", 1)[1].strip()
            if not token:
                return jsonify({"error": "missing or invalid authorization header"}), 401
            user = get_user_from_token(token)
            if user is None:
                return jsonify({"error": "invalid or expired token"}), 401
            return f(user, *args, **kwargs)
        return decorated

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad request"}), 400

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        username = username.strip()

        user_repo = get_user_repo()
        existing = user_repo.get_by_username(username)
        if existing is not None:
            return jsonify({"error": "username already taken"}), 409

        password_hash = generate_password_hash(password)
        user = user_repo.create_user(username, password_hash)
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
        username = username.strip()

        user = get_user_repo().get_by_username(username)
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = create_token(user["id"])
        return jsonify({"token": token})

    @app.route("/tasks", methods=["POST"])
    @require_auth
    def create_task(user):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        now = datetime.utcnow().isoformat()
        task_repo = get_task_repo()
        row = task_repo.create_task(title.strip(), "pending", now, user["id"])
        return jsonify(dict(row)), 201

    @app.route("/tasks", methods=["GET"])
    @require_auth
    def list_tasks(user):
        rows = get_task_repo().list_by_owner(user["id"])
        return jsonify([dict(r) for r in rows])

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    @require_auth
    def get_task(user, task_id):
        row = get_task_repo().get_by_id_and_owner(task_id, user["id"])
        if row is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(dict(row))

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    @require_auth
    def update_task(user, task_id):
        task_repo = get_task_repo()
        row = task_repo.get_by_id_and_owner(task_id, user["id"])
        if row is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True) or {}
        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400

        title = row["title"]
        status = row["status"]

        if "title" in data:
            new_title = data["title"]
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            title = new_title.strip()

        if "status" in data:
            new_status = data["status"]
            if not isinstance(new_status, str) or not new_status.strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            status = new_status.strip()

        just_completed = status == "completed" and row["status"] != "completed"

        updated = task_repo.update_task(task_id, title, status)

        if just_completed:
            # Fire-and-forget: a broker outage shouldn't fail the API response.
            try:
                send_notification_email.delay(user["username"], title)
            except Exception:
                app.logger.exception(
                    "Failed to enqueue notification email for task %s", task_id
                )

        return jsonify(dict(updated))

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
