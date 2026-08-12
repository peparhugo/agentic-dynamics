"""
Flask API for task management with JWT authentication.

MODELS:
- User: id (int, auto), username (str, unique), password_hash (str)
- Task: id (int, auto), title (str), status (str, default 'pending'),
        created_at (datetime), owner_id (int) FK -> users.id

ENDPOINTS:
- POST /auth/register   create a user (JSON body: {username, password})
- POST /auth/login      return a JWT token (JSON body: {username, password})
- POST /tasks           create a task (JSON body: {title: str})
- GET  /tasks           list the authenticated user's tasks by created_at desc
- GET  /tasks/{id}      get a single task owned by the user
- PUT  /tasks/{id}      update task title and/or status

AUTH:
- All /tasks/* endpoints require a valid JWT in the Authorization header
  as "Bearer <token>". Missing/invalid tokens return 401.
- Each user only sees/edits their own tasks.

STORAGE:
- SQLite. Schema is initialized on startup. A migration step adds the
  tasks.owner_id column when upgrading an existing database without
  destroying existing data.
"""

import os
import sqlite3
from functools import wraps
from datetime import datetime, timedelta, timezone

import jwt
from celery import Celery
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import celery_config

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY", "dev-secret-key"))
app.config.setdefault("JWT_EXPIRATION_HOURS", 24)


def create_celery():
    celery_app = Celery(
        __name__,
        broker=celery_config.broker_url,
        backend=celery_config.result_backend,
        include=["app"],
    )
    celery_app.conf.update(
        task_routes=celery_config.task_routes,
        task_serializer=celery_config.task_serializer,
        result_serializer=celery_config.result_serializer,
        accept_content=celery_config.accept_content,
        timezone=celery_config.timezone,
        enable_utc=celery_config.enable_utc,
    )
    return celery_app


celery = create_celery()


@celery.task(name="app.send_notification_email")
def send_notification_email(user_email, task_title):
    message = f"Mock email sent to {user_email}: your task '{task_title}' is completed."
    print(message)
    app.logger.info(message)
    return message


def user_email_from_row(user):
    if "email" in user.keys() and user["email"]:
        return user["email"]
    return user["username"]


def get_db():
    conn = sqlite3.connect(app.config.get("DATABASE", DATABASE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)")]
        if "owner_id" not in columns:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
        conn.commit()


def user_from_row(row):
    return {
        "id": row["id"],
        "username": row["username"],
    }


def task_from_row(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


def create_token(user_id, username):
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def get_current_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):]
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return row


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        request.current_user = user
        return fn(*args, **kwargs)

    return wrapper


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or not str(username).strip():
        return jsonify({"error": "username is required"}), 400
    if password is None or not str(password):
        return jsonify({"error": "password is required"}), 400
    username = str(username).strip()
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing is not None:
            return jsonify({"error": "username already taken"}), 409
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(str(password))),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(user_from_row(row)), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or password is None:
        return jsonify({"error": "username and password are required"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], str(password)):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(row["id"], row["username"])
    return jsonify({"token": token, "user": user_from_row(row)}), 200


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    user = request.current_user
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status") or "pending"
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, owner_id) VALUES (?, ?, ?)",
            (title, status, user["id"]),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(task_from_row(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    user = request.current_user
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (user["id"],),
        ).fetchall()
    return jsonify([task_from_row(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    user = request.current_user
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user["id"]),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_from_row(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    user = request.current_user
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        previous_status = row["status"]
        title = data.get("title", row["title"])
        status = data.get("status", row["status"])
        if title is None or not str(title).strip():
            return jsonify({"error": "title is required"}), 400
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (str(title).strip(), status, task_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if status == "completed" and previous_status != "completed":
        try:
            send_notification_email.delay(
                user_email_from_row(user), row["title"]
            )
        except Exception as exc:
            app.logger.error(
                "Failed to enqueue completion notification for task %s: %s",
                task_id,
                exc,
            )
    return jsonify(task_from_row(row))


init_db()


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
