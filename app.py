"""
Task API — Flask + SQLite with JWT authentication.

Endpoints:
    POST /auth/register       create a user
    POST /auth/login          obtain a JWT token
    POST /tasks               create a task (auth required)
    GET  /tasks               list own tasks ordered by created_at desc (auth required)
    GET  /tasks/{id}          get a single task (auth required)
    PUT  /tasks/{id}          update task title and/or status (auth required)
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import bcrypt
import jwt
from flask import Flask, jsonify, request

from tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    created_at TEXT NOT NULL,
    owner_id INTEGER NOT NULL REFERENCES users(id)
);
"""


# ── Database ────────────────────────────────────────────────────

def get_database_path():
    return app.config.get("DATABASE") or os.environ.get("DATABASE", "tasks.db")


def get_db():
    conn = sqlite3.connect(get_database_path())
    conn.row_factory = sqlite3.Row
    return conn


task_repository = TaskRepository(get_db)
user_repository = UserRepository(get_db)


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Migration: add owner_id to an existing tasks table without data loss.
        existing = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()
        if existing is not None:
            columns = {
                r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "owner_id" not in columns:
                conn.execute(
                    "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
                )
        conn.commit()


# ── Auth helpers ─────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def current_user():
    """Return the user row for the request's Authorization header, or None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return user_repository.get(user_id)


def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        request.user = user
        return f(*args, **kwargs)

    return wrapper


# ── Helpers ─────────────────────────────────────────────────────

def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def dispatch_completion_notification(user_email, task_title):
    """Enqueue the notification email without blocking the API response."""
    try:
        send_notification_email.delay(user_email, task_title)
    except Exception:
        app.logger.exception(
            "Failed to enqueue notification email for %s", user_email
        )


# ── Auth routes ─────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or str(username).strip() == "":
        return jsonify({"error": "username is required"}), 400
    if password is None or str(password) == "":
        return jsonify({"error": "password is required"}), 400
    username = str(username).strip()
    if user_repository.find_id_by_username(username) is not None:
        return jsonify({"error": "username already taken"}), 409
    user_id = user_repository.create(
        username=username, password_hash=hash_password(str(password))
    )
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or password is None:
        return jsonify({"error": "username and password are required"}), 400
    row = user_repository.get_by_username(str(username).strip())
    if row is None or not check_password(str(password), row["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(row["id"], row["username"])})


# ── Task routes (protected) ─────────────────────────────────────

@app.route("/tasks", methods=["POST"])
@auth_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or str(title).strip() == "":
        return jsonify({"error": "title is required"}), 400
    status = data.get("status") or "pending"
    now = datetime.utcnow().isoformat()
    owner_id = request.user["id"]
    task_id = task_repository.create(
        title=str(title).strip(), status=status, created_at=now, owner_id=owner_id
    )
    return jsonify({
        "id": task_id,
        "title": str(title).strip(),
        "status": status,
        "created_at": now,
    }), 201


@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks():
    rows = task_repository.list_for_owner(request.user["id"])
    return jsonify([serialize_task(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def get_task(task_id):
    row = task_repository.get_owned(task_id, request.user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(serialize_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def update_task(task_id):
    row = task_repository.get_owned(task_id, request.user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is not None:
        title = str(title).strip()
        if title == "":
            return jsonify({"error": "title cannot be empty"}), 400
    else:
        title = row["title"]
    status = data.get("status", row["status"])
    became_completed = status == "completed" and row["status"] != "completed"
    task_repository.update(task_id, title=title, status=status)
    if became_completed:
        dispatch_completion_notification(request.user["username"], title)
    return jsonify(serialize_task(task_repository.get_owned(task_id, request.user["id"])))


# ── Error handlers ──────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "method not allowed"}), 405


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
