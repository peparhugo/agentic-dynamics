import os
import sqlite3
import time
from functools import wraps

import jwt
from celery_config import celery_app, send_notification_email
from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash

from repositories import TaskRepository, UserRepository

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE = os.environ.get("DATABASE", "todos.db")

RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")
RATE_LIMIT_STORAGE = os.environ.get(
    "RATE_LIMIT_STORAGE", "redis://localhost:6379"
)


def rate_limit_key():
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if token:
        try:
            payload = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            return f"user:{payload['user_id']}"
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            pass
    return get_remote_address()


def on_breach_handler(request_limit):
    retry_after = max(1, int(request_limit.reset_at - time.time()))
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[RATE_LIMIT],
    storage_uri=RATE_LIMIT_STORAGE,
    on_breach=on_breach_handler,
    app=app,
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        "CREATE TABLE IF NOT EXISTS users ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  username TEXT NOT NULL UNIQUE,"
        "  password_hash TEXT NOT NULL,"
        "  email TEXT"
        ")"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS tasks ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT NOT NULL,"
        "  status TEXT NOT NULL DEFAULT 'pending',"
        "  created_at TEXT NOT NULL,"
        "  owner_id INTEGER,"
        "  FOREIGN KEY (owner_id) REFERENCES users (id)"
        ")"
    )
    try:
        db.execute(
            "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
        )
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass
    db.commit()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
        if not token:
            return jsonify({"error": "missing authorization token"}), 401
        try:
            payload = jwt.decode(token, app.secret_key, algorithms=["HS256"])
            g.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
        return f(*args, **kwargs)

    return decorated


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip() or None
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    db = get_db()
    user_repo = UserRepository(db)
    user = user_repo.create(username, password, email)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    db = get_db()
    user_repo = UserRepository(db)
    user = user_repo.get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode({"user_id": user["id"]}, app.secret_key, algorithm="HS256")
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    cursor = request.args.get("cursor", type=int)
    limit = request.args.get("limit", 20, type=int)
    limit = min(limit, 100)

    db = get_db()
    task_repo = TaskRepository(db)
    tasks = task_repo.list_by_owner_paginated(
        g.user_id, cursor=cursor, limit=limit + 1
    )
    has_more = len(tasks) > limit
    if has_more:
        tasks = tasks[:limit]

    total = task_repo.count_by_owner(g.user_id)
    next_cursor = tasks[-1]["id"] if has_more and tasks else None

    return jsonify({"data": tasks, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    db = get_db()
    task_repo = TaskRepository(db)
    task = task_repo.create(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    db = get_db()
    task_repo = TaskRepository(db)
    task = task_repo.get_by_id(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    db = get_db()
    task_repo = TaskRepository(db)
    user_repo = UserRepository(db)
    task = task_repo.update(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if task.get("status") == "completed":
        user_email = user_repo.get_email(g.user_id) or "unknown@example.com"
        send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
