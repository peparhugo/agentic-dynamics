"""
Flask API for task management.

Storage: SQLite (a single flat file on disk). The schema is initialized
on startup, including a migration that adds task ownership without
dropping existing data.
"""

from datetime import datetime, timedelta
import functools
import os
import sqlite3

import jwt
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from celery_app import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production!")
JWT_ALGORITHM = "HS256"
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "3600"))


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER
            )
            """
        )
        conn.commit()
        migrate(conn)


def migrate(conn):
    """Idempotent migration: add owner_id to existing tasks tables and
    preserve pre-existing data by assigning it to a legacy owner. Also
    add an optional email column to users for notifications."""
    task_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
    }
    if "owner_id" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()
    user_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    if "email" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()
    with conn:
        orphans = conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE owner_id IS NULL"
        ).fetchone()["n"]
        if orphans:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, password_hash) "
                "VALUES ('legacy', ?)",
                (generate_password_hash("legacy-default-password"),),
            )
            legacy = conn.execute(
                "SELECT id FROM users WHERE username = 'legacy'"
            ).fetchone()
            conn.execute(
                "UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL",
                (legacy["id"],),
            )


# ── Auth utilities ──────────────────────────────────────────────


def create_token(user_id):
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(seconds=TOKEN_TTL),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_user_from_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return UserRepository(DATABASE).get_by_id(int(user_id))


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401
        token = auth.split(" ", 1)[1].strip()
        user = get_user_from_token(token)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        return f(user, *args, **kwargs)

    return decorated


# ── Auth endpoints ──────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    email = (data.get("email") or "").strip() or None
    users = UserRepository(DATABASE)
    if users.find_by_username(username):
        return jsonify({"error": "username already taken"}), 409
    users.create(
        username=username,
        password_hash=generate_password_hash(password),
        email=email,
    )
    return jsonify({"message": "user registered", "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = UserRepository(DATABASE).find_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"])
    return jsonify({"token": token, "username": user["username"]})


# ── Task endpoints ──────────────────────────────────────────────


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task(user):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    status = (data.get("status") or "pending").strip() or "pending"
    created_at = datetime.utcnow().isoformat()
    task = TaskRepository(DATABASE).create(
        title=title, status=status, created_at=created_at, owner_id=user["id"]
    )
    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user):
    tasks = TaskRepository(DATABASE).list_by_owner(user["id"])
    return jsonify(tasks)


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user, task_id):
    task = TaskRepository(DATABASE).find_by_owner(task_id, user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user, task_id):
    data = request.get_json(silent=True) or {}
    tasks = TaskRepository(DATABASE)
    row = tasks.find_by_owner(task_id, user["id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    updated = tasks.update(task_id, title=title, status=status)
    if status == "completed" and row["status"] != "completed":
        user_email = user.get("email") or user["username"]
        try:
            send_notification_email.delay(user_email, title)
        except Exception:
            app.logger.exception(
                "Failed to enqueue completion notification for task %s", task_id
            )
    return jsonify(updated)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
