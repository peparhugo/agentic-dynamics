"""
Task Management API

A Flask REST API backed by SQLite with JWT authentication:
  - User: id (int, auto), username (str, unique), password_hash (str)
  - Task: id (int, auto), title (str), status (str, default 'pending'),
          owner_id (int), created_at (datetime)

All /tasks/* endpoints require a valid JWT in the Authorization header.
Each user only sees and manages their own tasks.
"""

import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

import jwt
from celery import Celery
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from celery_config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_ROUTES,
)
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

celery_app = Celery(
    "task_api",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_routes=CELERY_TASK_ROUTES,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
)

DATABASE = os.environ.get("TASK_DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("TASK_SECRET_KEY", "dev-secret-key-change-me")
TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))

VALID_STATUSES = {"pending", "in_progress", "completed"}


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


task_repository = TaskRepository(get_db)
user_repository = UserRepository(get_db)


def migrate_db():
    """Add owner_id to pre-existing databases without losing existing data."""
    with get_db() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "owner_id" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")

        legacy = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("legacy",)
        ).fetchone()
        if legacy is None:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("legacy", generate_password_hash("legacy-default-password")),
            )
        legacy_id = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("legacy",)
        ).fetchone()["id"]
        conn.execute(
            "UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL", (legacy_id,)
        )


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                owner_id INTEGER,
                created_at TEXT NOT NULL
            );
        """)
    migrate_db()


# ── Auth utilities ──────────────────────────────────────────────

def create_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def get_user_from_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("sub")
    except jwt.InvalidTokenError:
        return None
    if user_id is None:
        return None
    return user_repository.get_by_id(user_id)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401
        token = auth.split(" ", 1)[1]
        user = get_user_from_token(token)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        return f(user, *args, **kwargs)
    return decorated


# ── Notification (Celery) ───────────────────────────────────────

@celery_app.task(name="send_notification_email")
def send_notification_email(user_email: str, task_title: str):
    """Mock email notification: logs to the console instead of sending."""
    message = f"Task '{task_title}' completed - notifying {user_email}"
    app.logger.info("[email] %s", message)
    print(message)
    return {"status": "sent", "email": user_email, "task_title": task_title}


def owner_email(user: dict) -> str:
    """Derive a mock email address for a user (no email column exists)."""
    return f"{user['username']}@example.com"


def queue_notification_email(user_email: str, task_title: str):
    """Dispatch the notification email asynchronously via Celery."""
    send_notification_email.delay(user_email, task_title)


# ── Auth endpoints ──────────────────────────────────────────────

@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    if user_repository.get_by_username(username) is not None:
        return jsonify({"error": "username already taken"}), 409
    user_repository.create_user(username, generate_password_hash(password))
    return jsonify({"message": "user registered", "username": username}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    row = user_repository.get_by_username(username)
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(row["id"])
    return jsonify({"token": token, "username": row["username"]})


# ── Task endpoints (protected) ──────────────────────────────────

@app.post("/tasks")
@require_auth
def create_task(user: dict):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status", "pending")
    if status not in VALID_STATUSES:
        return jsonify({"error": "invalid status"}), 400
    now = datetime.utcnow().isoformat()
    task = task_repository.create(
        title=title, status=status, owner_id=user["id"], created_at=now
    )
    return jsonify(task), 201


@app.get("/tasks")
@require_auth
def list_tasks(user: dict):
    rows = task_repository.list_by_owner(user["id"])
    return jsonify(rows)


@app.get("/tasks/<int:task_id>")
@require_auth
def get_task(user: dict, task_id: int):
    row = task_repository.get_by_id_and_owner(task_id, user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(row)


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(user: dict, task_id: int):
    row = task_repository.get_by_id_and_owner(task_id, user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    if status not in VALID_STATUSES:
        return jsonify({"error": "invalid status"}), 400
    task_repository.update_for_owner(task_id, user["id"], title=title, status=status)
    if status == "completed" and row["status"] != "completed":
        queue_notification_email(owner_email(user), title)
    return jsonify({
        "id": task_id,
        "title": title,
        "status": status,
        "owner_id": user["id"],
        "created_at": row["created_at"],
    })


@app.delete("/tasks/<int:task_id>")
@require_auth
def delete_task(user: dict, task_id: int):
    if not task_repository.delete_for_owner(task_id, user["id"]):
        return jsonify({"error": "task not found"}), 404
    return jsonify({"message": "task deleted"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
