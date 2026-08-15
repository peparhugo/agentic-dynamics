"""
Flask Todo API with JWT authentication.

A single-file Flask app with clean structure: repositories, routes, error handling.
Each user authenticates with a username/password and sees only their own tasks.
"""

from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash
import sqlite3
import os

from celery_tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "dev-secret-change-me-0123456789abcdef"
)

jwt = JWTManager(app)


@jwt.invalid_token_loader
def _invalid_token_callback(reason):
    return jsonify({"error": "invalid token"}), 401


@jwt.expired_token_loader
def _expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"error": "token has expired"}), 401

DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _tasks_has_owner_id(conn) -> bool:
    rows = conn.execute("PRAGMA table_info(tasks)").fetchall()
    return any(r["name"] == "owner_id" for r in rows)


def _users_has_email(conn) -> bool:
    rows = conn.execute("PRAGMA table_info(users)").fetchall()
    return any(r["name"] == "email" for r in rows)


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
        # Migration: add email to a pre-existing users table without
        # destroying existing rows.
        if not _users_has_email(conn):
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER"
            ")"
        )
        # Migration: add owner_id to a pre-existing tasks table without
        # destroying existing rows.
        if not _tasks_has_owner_id(conn):
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


# ── Repositories ───────────────────────────────────────────────

user_repo = UserRepository(get_db)
task_repo = TaskRepository(get_db)


# ── Auth helpers ──────────────────────────────────────────────


def verify_user(username: str, password: str) -> dict | None:
    user = user_repo.find_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return None
    return user


def current_user_id() -> int:
    username = get_jwt_identity()
    user = user_repo.find_by_username(username)
    return user["id"] if user else None


def _trigger_completion_notification(owner_id: int, task_title: str):
    """Asynchronously notify a task owner that their task was completed."""
    user = user_repo.find_by_id(owner_id)
    if user is None:
        return
    user_email = user.get("email") or f"{user['username']}@example.com"
    send_notification_email.delay(user_email, task_title)


# ── Routes ─────────────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username:
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400
    user = user_repo.create(username, password, data.get("email"))
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401
    token = create_access_token(identity=username)
    return jsonify({"access_token": token}), 200


@app.route("/tasks", methods=["GET"])
@jwt_required()
def list_tasks():
    return jsonify(task_repo.list_by_owner(current_user_id()))


@app.route("/tasks", methods=["POST"])
@jwt_required()
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create(title, current_user_id())
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@jwt_required()
def show_task(task_id: int):
    task = task_repo.get(task_id, current_user_id())
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@jwt_required()
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    owner_id = current_user_id()
    before = task_repo.get(task_id, owner_id)
    task = task_repo.update(
        task_id,
        owner_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if task["status"] == "completed" and (
        before is None or before.get("status") != "completed"
    ):
        _trigger_completion_notification(owner_id, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
