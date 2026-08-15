"""Flask task management API with SQLite persistence and JWT authentication."""

import os
import time
import sqlite3
from functools import wraps

import jwt
from flask import Flask, g, request, jsonify
from flask_limiter import Limiter, RateLimitExceeded
from werkzeug.security import check_password_hash, generate_password_hash

from celery_config import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")


def _rate_limit_key():
    auth = request.headers.get("Authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            try:
                payload = jwt.decode(parts[1], SECRET_KEY, algorithms=["HS256"])
                return "user:" + str(payload["sub"])
            except Exception:
                pass
    return "ip:" + (request.remote_addr or "anonymous")


limiter = Limiter(
    key_func=_rate_limit_key,
    default_limits=[RATE_LIMIT],
    storage_uri=REDIS_URL,
)
limiter.init_app(app)


@app.errorhandler(429)
def ratelimit_handler(e):
    retry_after = "60"
    if isinstance(e, RateLimitExceeded):
        try:
            retry_after = str(int(e.limit.limit.get_expiry()))
        except Exception:
            retry_after = "60"
    response = jsonify({"error": "rate limit exceeded"})
    response.headers["Retry-After"] = retry_after
    return response, 429


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email TEXT
        )
        """
    )
    conn.commit()

    # Migration: add owner_id to existing tasks table without breaking data.
    columns = _table_columns(conn, "tasks")
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()

    # Migration: add email to existing users table without breaking data.
    columns = _table_columns(conn, "users")
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()

    conn.close()


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization")
        if not auth:
            return jsonify({"error": "missing authorization header"}), 401
        parts = auth.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "invalid authorization header"}), 401
        token = parts[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = int(payload["sub"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return jsonify({"error": "invalid token"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)

    return wrapper


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or not str(username).strip():
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400
    username = str(username).strip()

    conn = get_db()
    users = UserRepository(conn)
    if users.find_by_username(username) is not None:
        conn.close()
        return jsonify({"error": "username already exists"}), 409

    password_hash = generate_password_hash(password)
    email = data.get("email")
    if email is not None:
        email = str(email).strip() or None
    user_id = users.create_user(username, password_hash, email)
    conn.close()
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    conn = get_db()
    users = UserRepository(conn)
    row = users.find_by_username(username)
    conn.close()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    token = jwt.encode(
        {"sub": str(row["id"]), "iat": int(time.time())},
        SECRET_KEY,
        algorithm="HS256",
    )
    return jsonify({"token": token})


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    now = int(time.time())
    conn = get_db()
    tasks = TaskRepository(conn)
    task_id = tasks.create_task(title, now, g.user_id)
    conn.close()
    return jsonify(
        {"id": task_id, "title": title, "status": "pending", "created_at": now}
    ), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    limit = request.args.get("limit", "20")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid limit"}), 400
    if limit < 1:
        return jsonify({"error": "invalid limit"}), 400
    limit = min(limit, 100)

    cursor = request.args.get("cursor")
    if cursor is not None:
        try:
            cursor = int(cursor)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid cursor"}), 400

    conn = get_db()
    tasks = TaskRepository(conn)
    rows = tasks.find_by_owner_paginated(g.user_id, cursor, limit)
    total = tasks.count_by_owner(g.user_id)
    conn.close()

    has_more = len(rows) > limit
    page_rows = rows[:limit]
    data = [task_to_dict(r) for r in page_rows]
    next_cursor = None
    if has_more and page_rows:
        next_cursor = str(page_rows[-1]["id"])
    return jsonify({"data": data, "next_cursor": next_cursor, "total": total})


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    conn = get_db()
    tasks = TaskRepository(conn)
    row = tasks.get_by_id_and_owner(task_id, g.user_id)
    conn.close()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    conn = get_db()
    tasks = TaskRepository(conn)
    users = UserRepository(conn)
    row = tasks.get_by_id_and_owner(task_id, g.user_id)
    if row is None:
        conn.close()
        return jsonify({"error": "task not found"}), 404

    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    if title is not None:
        title = str(title).strip()
        if not title:
            conn.close()
            return jsonify({"error": "title is required"}), 400
    if not status:
        conn.close()
        return jsonify({"error": "status is required"}), 400

    was_completed = row["status"] == "completed"

    tasks.update(task_id, title=title, status=status)
    updated = tasks.get_by_id(task_id)
    owner_email = users.email_for(g.user_id)
    conn.close()

    if status == "completed" and not was_completed:
        send_notification_email.delay(owner_email, title)

    return jsonify(task_to_dict(updated))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
