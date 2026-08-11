from flask import Flask, request, jsonify, g
from datetime import datetime, timezone, timedelta
import sqlite3
import os
import jwt
import bcrypt
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery_config import send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["RATELIMIT_LIMIT"] = os.environ.get("RATELIMIT_LIMIT", "100 per minute")

DATABASE = os.environ.get("DATABASE", "tasks.db")


def _get_rate_limit_key():
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:]
        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            return str(data["user_id"])
        except Exception:
            pass
    return get_remote_address()


def _get_rate_limit_limit():
    return app.config.get("RATELIMIT_LIMIT", "100 per minute")


def _on_rate_limit_breach(request_limit):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    return response


limiter = Limiter(
    key_func=_get_rate_limit_key,
    storage_uri=os.environ.get("LIMITER_STORAGE_URI", "redis://localhost:6379"),
    default_limits=[_get_rate_limit_limit],
    headers_enabled=True,
    retry_after="delta-seconds",
    on_breach=_on_rate_limit_breach,
)
limiter.init_app(app)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


user_repo = UserRepository(get_db)
task_repo = TaskRepository(get_db)


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        cols = conn.execute("PRAGMA table_info(tasks)").fetchall()
        col_names = [c["name"] for c in cols]
        if "owner_id" not in col_names:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
        conn.commit()


def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth[7:]

        if not token:
            return jsonify({"error": "token is missing"}), 401

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            g.user_id = data["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "token is invalid"}), 401

        return f(*args, **kwargs)

    return decorated


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    existing = user_repo.find_by_username(username)
    if existing:
        return jsonify({"error": "username already exists"}), 409

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    user_id = user_repo.create(username, password_hash)

    token = create_token(user_id)
    return jsonify({"token": token, "user_id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_repo.find_by_username(username)
    if not user:
        return jsonify({"error": "invalid username or password"}), 401

    if not bcrypt.checkpw(
        password.encode("utf-8"), user["password_hash"].encode("utf-8")
    ):
        return jsonify({"error": "invalid username or password"}), 401

    user_id = user["id"]

    token = create_token(user_id)
    return jsonify({"token": token, "user_id": user_id, "username": username}), 200


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    task = task_repo.create(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    cursor = request.args.get("cursor", type=int, default=None)
    limit = request.args.get("limit", type=int, default=20)
    limit = max(1, min(limit, 100))
    result = task_repo.find_by_owner_paginated(g.user_id, cursor=cursor, limit=limit)
    return jsonify(result)


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    task = task_repo.find_by_id_and_owner(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    status = data.get("status")

    task = task_repo.find_by_id_and_owner(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    old_status = task["status"]
    old_title = task["title"]

    updates = {}

    if title is not None:
        title = title.strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        updates["title"] = title

    if status is not None:
        updates["status"] = status

    task = task_repo.update(task_id, updates)

    if status is not None and status == "completed" and old_status != "completed":
        user = user_repo.find_by_id(g.user_id)
        if user:
            user_email = f"{user['username']}@example.com"
            task_title_for_email = title if title is not None else old_title
            send_notification_email.delay(user_email, task_title_for_email)

    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
