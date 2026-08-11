from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import functools
import jwt
import sqlite3
import os

from celery_config import send_notification_email
from repositories.task_repository import TaskRepository
from repositories.user_repository import UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SECRET_KEY"] = SECRET_KEY

RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "redis://localhost:6379")
RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "100 per minute")


def rate_limit_key():
    if request.endpoint and request.endpoint.startswith("auth."):
        return get_remote_address()
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header[7:]
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return str(payload["user_id"])
        except Exception:
            pass
    return get_remote_address()


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    storage_uri=RATELIMIT_STORAGE_URL,
    default_limits=[RATELIMIT_DEFAULT],
    retry_after="http-date",
)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


task_repo = TaskRepository(get_db)
user_repo = UserRepository(get_db)


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        except sqlite3.OperationalError:
            pass


def token_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return jsonify({"error": "token is missing"}), 401
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "token is invalid"}), 401
        return f(current_user_id, *args, **kwargs)
    return decorated


def generate_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip() or None
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.create(username, password, email)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks(current_user_id: int):
    cursor = request.args.get("cursor")
    limit = request.args.get("limit", 20, type=int)

    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100

    if cursor is not None:
        try:
            cursor = int(cursor)
        except (ValueError, TypeError):
            cursor = None

    data, next_cursor = task_repo.get_all_paginated(current_user_id, cursor, limit)
    total = task_repo.count_all(current_user_id)

    return jsonify({
        "data": data,
        "next_cursor": next_cursor,
        "total": total,
    })


@app.route("/tasks", methods=["POST"])
@token_required
def add_task(current_user_id: int):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, current_user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def show_task(current_user_id: int, task_id: int):
    task = task_repo.get_by_id(task_id, current_user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def edit_task(current_user_id: int, task_id: int):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    old_task = task_repo.get_by_id(task_id, current_user_id)
    if old_task is None:
        return jsonify({"error": "task not found"}), 404
    task = task_repo.update(
        task_id,
        current_user_id,
        title=data.get("title"),
        status=new_status,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if new_status == "completed" and old_task["status"] != "completed":
        user = user_repo.get_by_id(current_user_id)
        if user and user.get("email"):
            send_notification_email.delay(user["email"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
