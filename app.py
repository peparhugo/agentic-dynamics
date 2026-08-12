"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.

Session 2: JWT authentication added.
  - New User model (id, username, password_hash)
  - POST /auth/register and POST /auth/login
  - All /tasks/* endpoints require a valid JWT
  - Each user only sees their own tasks (Task.owner_id)

Session 3: Async email notifications.
  - Celery + Redis for background jobs
  - When a task transitions to 'completed', enqueue send_notification_email
    to the task owner (email is optional on register, defaults to
    <username>@example.com)

Session 4: Repository pattern.
  - All SQLite access moved into repository classes (repositories.py)
  - Route handlers call repository methods, never raw SQL
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import jwt

from tasks import send_notification_email

from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
TOKEN_TTL_HOURS = 24


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )
        # Migration: add owner_id to pre-existing tasks tables without it.
        cols = [row[1] for row in conn.execute("PRAGMA table_info(tasks)")]
        if "owner_id" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        # Migration: add email to pre-existing users tables without it.
        user_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
        if "email" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


# ── Repositories ────────────────────────────────────────────


task_repo = TaskRepository(get_db)
user_repo = UserRepository(get_db)


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    import re
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated

# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


def generate_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        return None


def notify_task_completed(owner_id: int, task_title: str) -> None:
    """Enqueue an async notification email to the task owner.

    Dispatch is non-blocking: the task is sent to Celery (Redis broker)
    and the API response returns immediately.
    """
    user = user_repo.get_user(owner_id)
    if user is None:
        return
    user_email = user.get("email") or f"{user['username']}@example.com"
    send_notification_email.delay(user_email, task_title)


# ── Auth helpers ──────────────────────────────────────────────


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
        user_id = decode_token(token) if token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return wrapper


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repo.get_user_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 400
    user = user_repo.create_user(username, password)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user = user_repo.get_user_by_username(username)
    if user is None or not user_repo.verify_password(user, password):
        return jsonify({"error": "invalid credentials"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(task_repo.get_tasks(g.user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create_task(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repo.get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    previous = task_repo.get_task(task_id, g.user_id)
    task = task_repo.update_task(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        task["status"] == "completed"
        and (previous is None or previous["status"] != "completed")
    ):
        notify_task_completed(g.user_id, task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
