"""
Task Management API

A Flask API backed by SQLite that provides CRUD operations for tasks.
Tasks are scoped to authenticated users via JWT authentication.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
import sqlite3
import os

import jwt
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from werkzeug.security import generate_password_hash, check_password_hash

from repositories import TaskRepository, UserRepository
from tasks import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 24

RATE_LIMIT_STORAGE_URI = os.environ.get(
    "RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/0"
)
RATE_LIMIT_PER_MINUTE = 100


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


task_repo = TaskRepository(get_db)
user_repo = UserRepository(get_db)


def migrate(conn):
    """Additive migrations so existing data is preserved."""
    task_cols = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "owner_id" not in task_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
    user_cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "email" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)
        migrate(conn)
        conn.commit()


def _row_to_task(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


def make_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing token"}), 401
        token = auth[len("Bearer "):]
        try:
            payload = decode_token(token)
        except jwt.PyJWTError:
            return jsonify({"error": "invalid token"}), 401
        request.user_id = int(payload["sub"])
        request.username = payload["username"]
        return fn(*args, **kwargs)
    return wrapper


def _rate_limit_key() -> str:
    """Identify the authenticated user (or remote address for unauthenticated
    requests such as the auth endpoints) so limits apply per user."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            payload = decode_token(auth[len("Bearer "):])
            return f"user:{payload['sub']}"
        except jwt.PyJWTError:
            pass
    return f"ip:{request.remote_addr or 'unknown'}"


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=RATE_LIMIT_STORAGE_URI,
    application_limits=[f"{RATE_LIMIT_PER_MINUTE} per minute"],
    retry_after="delta-seconds",
    headers_enabled=True,
)
limiter.init_app(app)


@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(_error):
    return jsonify({"error": "rate limit exceeded"}), 429


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password")
    if not username:
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    password_hash = generate_password_hash(password)
    email = (data.get("email") or "").strip() or username
    try:
        user_id = user_repo.create_user(username, password_hash, email)
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username, "email": email}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    row = user_repo.find_by_username(username)
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify(
        {"token": make_token(row["id"], row["username"]), "username": row["username"]}
    ), 200


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    status = data.get("status", "pending")
    now = datetime.now(timezone.utc).isoformat()
    row = task_repo.create_task(title.strip(), status, now, request.user_id)
    return jsonify(_row_to_task(row)), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    try:
        limit = int(request.args.get("limit", "20"))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be a positive integer"}), 400
    if limit < 1:
        return jsonify({"error": "limit must be a positive integer"}), 400
    limit = min(limit, 100)

    cursor_param = request.args.get("cursor")
    cursor = None
    if cursor_param is not None:
        try:
            cursor = int(cursor_param)
        except ValueError:
            return jsonify({"error": "cursor must be an integer"}), 400

    rows = task_repo.list_for_owner_page(request.user_id, cursor, limit + 1)
    has_more = len(rows) > limit
    rows = rows[:limit]
    data = [_row_to_task(r) for r in rows]
    total = task_repo.count_for_owner(request.user_id)
    next_cursor = str(data[-1]["id"]) if has_more and data else None
    return jsonify({"data": data, "next_cursor": next_cursor, "total": total})


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id: int):
    row = task_repo.get_for_owner(task_id, request.user_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(_row_to_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    row = task_repo.get_for_owner(task_id, request.user_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    if "title" in data and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title is required"}), 400
    if "status" in data and not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400
    task_repo.update(task_id, {"title": title.strip(), "status": status})
    updated = task_repo.get_by_id(task_id)
    if row["status"] != "completed" and updated["status"] == "completed":
        user = user_repo.get_by_id(request.user_id)
        user_email = (user["email"] if user and user["email"] else None) or request.username
        send_notification_email.delay(user_email, updated["title"])
    return jsonify(_row_to_task(updated))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(debug=True)
