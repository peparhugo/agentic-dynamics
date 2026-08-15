"""
Flask task management API with SQLite storage.

Models: User (id, username, password_hash, email), Task (id, title, status, created_at, owner_id)
Status values: 'pending' (default) or 'done'
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import sys
import jwt
from celery_tasks import send_notification_email
from repositories import UserRepository, TaskRepository
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
limiter = Limiter(
    app=app,
    key_func=lambda: _get_current_user_id() or get_remote_address(),
    default_limits=["100/minute"],
    storage_uri="memory://"
)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
VALID_STATUSES = {"pending", "done"}

_app_module = sys.modules[__name__]
user_repo = UserRepository(_app_module)
task_repo = TaskRepository(_app_module)


def _get_current_user_id():
    """Extract user ID from JWT token in current request for rate limiting."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return str(data.get("user_id"))
    except:
        return None


def _get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT UNIQUE NOT NULL,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER,"
            "  FOREIGN KEY (owner_id) REFERENCES users(id)"
            ")"
        )
        conn.commit()
        migrate_tasks_add_owner()
        migrate_users_add_email()


def migrate_tasks_add_owner():
    """Migrate existing tasks without owner_id to have owner_id = NULL."""
    with _get_db() as conn:
        cursor = conn.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            conn.commit()


def migrate_users_add_email():
    """Migrate existing users without email to have email = NULL."""
    with _get_db() as conn:
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "email" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
            conn.commit()


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"error": "Invalid token format"}), 401

        if not token:
            return jsonify({"error": "Missing token"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = data.get("user_id")
            if user_id is None:
                return jsonify({"error": "Invalid token"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(user_id, *args, **kwargs)
    return decorated




@app.route("/auth/register", methods=["POST"])
@limiter.limit("100/minute")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip() if data.get("email") else None

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_repo.create(username, password, email)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
@limiter.limit("100/minute")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_repo.verify(username, password)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401

    token = jwt.encode(
        {
            "user_id": user["id"],
            "username": user["username"],
            "exp": datetime.utcnow() + timedelta(hours=24),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@token_required
@limiter.limit("100/minute")
def list_tasks(user_id):
    cursor = request.args.get("cursor", type=int, default=None)
    limit = request.args.get("limit", type=int, default=20)

    # Validate limit
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100

    result = task_repo.get_paginated(user_id, cursor=cursor, limit=limit)
    return jsonify(result)


@app.route("/tasks", methods=["POST"])
@token_required
@limiter.limit("100/minute")
def add_task(user_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
@limiter.limit("100/minute")
def show_task(user_id, task_id: int):
    task = task_repo.get_by_id(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
@limiter.limit("100/minute")
def edit_task(user_id, task_id: int):
    task = task_repo.get_by_id(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "status" in data and data["status"] not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status: {data['status']}"}), 422

    old_status = task.get("status")
    should_notify = "status" in data and data["status"] == "done" and old_status != "done"

    updated_task = task_repo.update(
        task_id,
        user_id,
        title=data.get("title"),
        status=data.get("status"),
    )

    if should_notify:
        user_email = user_repo.get_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, task["title"])

    return jsonify(updated_task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
