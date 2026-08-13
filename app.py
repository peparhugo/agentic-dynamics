"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import jwt

from notifications import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 60


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Repositories receive `get_db` itself (not a connection), so they always
# resolve the current DATABASE at call time — important since callers (and
# tests) may repoint DATABASE after the app module has already loaded.
user_repository = UserRepository(get_db)
task_repository = TaskRepository(get_db)


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
            ")"
        )
        _migrate_add_owner_id(conn)
        _migrate_add_email(conn)


def _migrate_add_owner_id(conn):
    """Add owner_id to a pre-existing tasks table that predates auth, if missing."""
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def _migrate_add_email(conn):
    """Add email to a pre-existing users table that predates notifications, if missing."""
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


# ── Models: users ────────────────────────────────────────────────


def create_user(username: str, password: str, email: str | None = None) -> dict:
    password_hash = generate_password_hash(password)
    email = email or f"{username}@example.com"
    return user_repository.create(username, password_hash, email)


def get_user_by_username(username: str) -> dict | None:
    return user_repository.get_by_username(username)


def get_user_by_id(user_id: int) -> dict | None:
    return user_repository.get_by_id(user_id)


# ── Models: tasks ─────────────────────────────────────────────────


def create_task(title: str, owner_id: int) -> dict:
    now = datetime.utcnow().isoformat()
    return task_repository.create(title, owner_id, now)


def get_tasks(owner_id: int):
    return task_repository.list_for_owner(owner_id)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return task_repository.get_for_owner(task_id, owner_id)


def update_task(
    task_id: int, owner_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    return task_repository.update_for_owner(task_id, owner_id, title=title, status=status)


# ── Auth helpers ──────────────────────────────────────────────────


def generate_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXP_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[len("Bearer "):]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except jwt.PyJWTError:
            return jsonify({"error": "missing or invalid token"}), 401
        user = get_user_by_id(payload.get("sub"))
        if user is None:
            return jsonify({"error": "missing or invalid token"}), 401
        g.user_id = user["id"]
        return f(*args, **kwargs)

    return wrapper


# ── Routes: auth ──────────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip() or None
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if get_user_by_username(username) is not None:
        return jsonify({"error": "username already taken"}), 400
    user = create_user(username, password, email)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token})


# ── Routes: tasks ─────────────────────────────────────────────────


@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    return jsonify(get_tasks(g.user_id))


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    previous_task = get_task(task_id, g.user_id)
    task = update_task(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=new_status,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if new_status == "completed" and previous_task["status"] != "completed":
        owner = get_user_by_id(g.user_id)
        send_notification_email.delay(owner["email"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
