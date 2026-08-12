import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, current_app, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash

from celery_config import send_notification_email
from repositories.user_repository import UserRepository
from repositories.task_repository import TaskRepository

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key"


def _rate_limit_key():
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            return f"user:{payload['user_id']}"
        except Exception:
            pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=app.config.get("RATELIMIT_STORAGE_URI", "redis://localhost:6379"),
    default_limits=["100 per minute"],
)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db_path = current_app.config.get("DATABASE", "tasks.db")
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db


def get_user_repo():
    return UserRepository(get_db())


def get_task_repo():
    return TaskRepository(get_db())


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            owner_id INTEGER REFERENCES user(id)
        )
        """
    )
    try:
        db.execute(
            "ALTER TABLE task ADD COLUMN owner_id INTEGER REFERENCES user(id)"
        )
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE user ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Missing or invalid token"}), 401
        user_repo = get_user_repo()
        if not user_repo.exists_by_id(payload["user_id"]):
            return jsonify({"error": "Missing or invalid token"}), 401
        g.current_user_id = payload["user_id"]
        return f(*args, **kwargs)

    return decorated


limiter.init_app(app)


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password are required"}), 400

    username = data["username"]
    password = data["password"]
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "Username and password are required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "Username and password are required"}), 400

    user_repo = get_user_repo()
    if user_repo.exists_by_username(username.strip()):
        return jsonify({"error": "Username already exists"}), 409

    password_hash = generate_password_hash(password)
    email = data.get("email", f"{username.strip()}@example.com")
    user = user_repo.create(username.strip(), password_hash, email)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Username and password are required"}), 400

    username = data["username"]
    password = data["password"]

    user_repo = get_user_repo()
    user = user_repo.find_by_username(username)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    payload = {
        "user_id": user["id"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    token = jwt.encode(
        payload, current_app.config["SECRET_KEY"], algorithm="HS256"
    )
    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json(silent=True)
    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    title = data["title"]
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "Title is required"}), 400

    now = datetime.now(timezone.utc).isoformat()
    task_repo = get_task_repo()
    task = task_repo.create(
        owner_id=g.current_user_id,
        title=title.strip(),
        status="pending",
        created_at=now,
    )
    return jsonify(task_to_dict(task)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    task_repo = get_task_repo()
    cursor_param = request.args.get("cursor")
    cursor = int(cursor_param) if cursor_param else None
    try:
        limit = int(request.args.get("limit", 20))
    except ValueError:
        limit = 20
    limit = max(1, min(limit, 100))
    data, next_cursor = task_repo.find_all_by_owner_paginated(
        g.current_user_id, cursor, limit
    )
    total = task_repo.count_by_owner(g.current_user_id)
    return jsonify({"data": [task_to_dict(t) for t in data], "next_cursor": next_cursor, "total": total}), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    task_repo = get_task_repo()
    task = task_repo.find_by_id(task_id, g.current_user_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task_to_dict(task)), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    task_repo = get_task_repo()
    task = task_repo.find_by_id(task_id, g.current_user_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify(task_to_dict(task)), 200

    title = data.get("title", task["title"])
    status = data.get("status", task["status"])

    if isinstance(title, str) and not title.strip():
        return jsonify({"error": "Title is required"}), 400

    final_title = title.strip() if isinstance(title, str) else title
    task_repo.update(task_id, g.current_user_id, final_title, status)

    if task["status"] != "completed" and status == "completed":
        user_repo = get_user_repo()
        email = user_repo.get_email(g.current_user_id)
        send_notification_email.delay(email, task["title"])

    task = task_repo.find_by_id(task_id, g.current_user_id)
    return jsonify(task_to_dict(task)), 200


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
