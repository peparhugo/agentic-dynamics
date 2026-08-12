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
import jwt
import bcrypt

from repositories import UserRepository, TaskRepository

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-do-not-use-in-prod")

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def get_db():
    conn = sqlite3.connect(app.config.get("DATABASE", DATABASE))
    conn.row_factory = sqlite3.Row
    return conn


user_repo = UserRepository(get_db)
task_repo = TaskRepository(get_db)


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass


# ── Auth helpers ─────────────────────────────────────────────────

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[7:]
        try:
            payload = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=[JWT_ALGORITHM]
            )
            g.user_id = payload["user_id"]
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"error": "missing or invalid token"}), 401
        return f(*args, **kwargs)

    return decorated


# ── Auth utilities ───────────────────────────────────────────────

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=JWT_ALGORITHM)


# ── Notification helper ──────────────────────────────────────────

def notify_task_completion(user_email, task_title):
    from celery_tasks import send_notification_email
    send_notification_email.delay(user_email, task_title)


# ── Auth routes ──────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
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
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.find_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token})


# ── Task routes ──────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(task_repo.find_all(g.user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repo.find_by_id(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    existing_task = task_repo.find_by_id(task_id, g.user_id)
    task = task_repo.update(
        task_id, g.user_id, title=data.get("title"), status=new_status
    )
    if task is None:
        if task_repo.exists(task_id):
            return jsonify({"error": "task not found"}), 404
        title = data.get("title", "").strip()
        if title:
            task = task_repo.create(title, g.user_id)
        else:
            return jsonify({}), 200
    else:
        old_status = existing_task["status"] if existing_task else None
        if task["status"] == "completed" and old_status != "completed":
            user = user_repo.find_by_id(g.user_id)
            user_email = (user.get("email") if user else None) or ""
            if user_email:
                notify_task_completion(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
