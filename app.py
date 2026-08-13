"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import jwt
from functools import wraps
from werkzeug.security import check_password_hash
from celery_tasks import send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

user_repo = UserRepository()
task_repo = TaskRepository()


def get_database_path():
    return os.environ.get("DATABASE", "todos.db")


def get_db():
    conn = sqlite3.connect(get_database_path())
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
            "  owner_id INTEGER NOT NULL,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  FOREIGN KEY (owner_id) REFERENCES users(id)"
            ")"
        )
        conn.commit()



# ── Auth ──────────────────────────────────────────────────────


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def generate_token(user_id: int) -> str:
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


def verify_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload['user_id']
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError, KeyError):
        return None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                pass

        if not token:
            return jsonify({"error": "missing token"}), 401

        user_id = verify_token(token)
        if user_id is None:
            return jsonify({"error": "invalid token"}), 401

        return f(user_id, *args, **kwargs)
    return decorated




# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_repo.create(username, password, email if email else None)
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

    user = user_repo.get_by_username(username)
    if user is None or not verify_password(password, user['password_hash']):
        return jsonify({"error": "invalid username or password"}), 401

    token = generate_token(user['id'])
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks(user_id):
    return jsonify(task_repo.get_for_user(user_id))


@app.route("/tasks", methods=["POST"])
@token_required
def add_task(user_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(user_id, title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def show_task(user_id, task_id: int):
    task = task_repo.get(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def edit_task(user_id, task_id: int):
    data = request.get_json(silent=True) or {}
    old_task = task_repo.get(task_id, user_id)
    if old_task is None:
        return jsonify({"error": "task not found"}), 404

    task = task_repo.update(
        task_id,
        user_id,
        title=data.get("title"),
        status=data.get("status"),
    )

    if task and data.get("status") == "completed" and old_task.get("status") != "completed":
        user = user_repo.get_by_id(user_id)
        if user and user.get("email"):
            send_notification_email.delay(user["email"], task["title"])

    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
