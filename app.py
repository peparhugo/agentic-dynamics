"""
Codebase seed — Minimal Flask Todo API with JWT auth.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash
from functools import wraps
import sqlite3
import jwt
import os

from celery_tasks import send_notification_email
from repositories.task_repository import TaskRepository
from repositories.user_repository import UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")


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
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER,"
            "  FOREIGN KEY (owner_id) REFERENCES users(id)"
            ")"
        )


def migrate():
    with get_db() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "  username TEXT NOT NULL UNIQUE,"
                "  password_hash TEXT NOT NULL,"
                "  email TEXT"
                ")"
            )
        user_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")


# ── Auth decorator ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "unauthorized"}), 401
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            g.user_id = payload["user_id"]
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── Auth helpers ────────────────────────────────────────────────

def generate_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


# ── Auth routes ───────────────────────────────────────────────

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

    user = user_repo.find_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    token = generate_token(user["id"])
    return jsonify({"token": token}), 200


# ── Task routes ───────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    return jsonify(task_repo.find_all_by_owner(g.user_id))


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = task_repo.find_by_id(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    old_task = task_repo.find_by_id(task_id, g.user_id)

    task = task_repo.update(
        task_id,
        g.user_id,
        title=data.get("title"),
        status=new_status,
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404

    if new_status == "completed" and old_task and old_task.get("status") != "completed":
        user = user_repo.find_by_id(g.user_id)
        if user:
            email = user.get("email") or f"{user['username']}@example.com"
            send_notification_email.delay(email, task["title"])

    return jsonify(task)


if __name__ == "__main__":
    init_db()
    migrate()
    app.run(debug=True)
