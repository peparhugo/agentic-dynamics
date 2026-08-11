"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import bcrypt
import jwt
from tasks import send_notification_email
from repository import TaskRepository, UserRepository

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

DATABASE = os.environ.get("DATABASE", "todos.db")


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
            "  password_hash TEXT NOT NULL"
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
        columns = [col[1] for col in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        user_columns = [col[1] for col in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")


# ── Repositories ───────────────────────────────────────────────

task_repo = TaskRepository(get_db)
user_repo = UserRepository(get_db)


# ── Auth ──────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        if not token:
            return jsonify({"error": "missing token"}), 401

        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            g.current_user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401

        return f(*args, **kwargs)
    return decorated


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if user_repo.find_by_username(username):
        return jsonify({"error": "username already exists"}), 409

    email = data.get("email", f"{username}@example.com")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user_id = user_repo.create(username, password_hash, email)

    return jsonify({"id": user_id, "username": username, "email": email}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_repo.find_by_username(username)
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error": "invalid credentials"}), 401

    token = jwt.encode(
        {"user_id": user["id"], "exp": datetime.utcnow() + timedelta(hours=24)},
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    return jsonify(task_repo.find_all_by_owner(g.current_user_id))


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    title = request.json['title']
    task = task_repo.create(title, g.current_user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = task_repo.find_by_id_and_owner(task_id, g.current_user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = task_repo.update(
        task_id,
        g.current_user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404

    if data.get("status") == "completed":
        user = user_repo.find_by_id(g.current_user_id)
        if user and user.get("email"):
            send_notification_email.delay(user["email"], task["title"])

    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
