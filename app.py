from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import secrets

import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded

from celery_app import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATABASE = os.environ.get("DATABASE", "tasks.db")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "3600"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "100"))
RATE_LIMIT_STORAGE_URI = os.environ.get(
    "RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/0"
)
app.config["RATE_LIMIT_PER_MINUTE"] = RATE_LIMIT_PER_MINUTE

task_repo = TaskRepository(DATABASE)
user_repo = UserRepository(DATABASE)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)
        migrate_tasks_owner_id(conn)
        migrate_users_email(conn)


def migrate_tasks_owner_id(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def migrate_users_email(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


def resolve_user_email(user_id, fallback):
    return user_repo.email_for(user_id) or fallback


def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


# ── Auth utilities ─────────────────────────────────────────────


def create_token(user):
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=TOKEN_TTL),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def get_user_from_token(token):
    try:
        payload = jwt.decode(
            token, app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    return payload


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth.split(" ", 1)[1].strip()
        if not token:
            return jsonify({"error": "missing or invalid token"}), 401
        user = get_user_from_token(token)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        return f(user, *args, **kwargs)
    return decorated


# ── Rate limiting ──────────────────────────────────────────────


def get_rate_limit_key():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1].strip()
        payload = get_user_from_token(token)
        if payload is not None:
            return f"user:{payload['user_id']}"
    remote = request.access_route[0] if request.access_route else request.remote_addr
    return f"ip:{remote or 'unknown'}"


def get_default_limits():
    return f"{app.config['RATE_LIMIT_PER_MINUTE']} per minute"


_rate_limit_storage_options = {}
if os.environ.get("FAKE_REDIS", "").lower() in ("1", "true", "yes"):
    import fakeredis

    _rate_limit_storage_options["connection_pool"] = fakeredis.FakeRedis(
        decode_responses=True
    ).connection_pool

limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[get_default_limits],
    storage_uri=RATE_LIMIT_STORAGE_URI,
    storage_options=_rate_limit_storage_options,
    headers_enabled=True,
    retry_after="delta-seconds",
)
limiter.init_app(app)


@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(e):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    return response


# ── Auth endpoints ─────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    email = str(data.get("email", "")).strip() or None
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if user_repo.username_exists(username):
        return jsonify({"error": "username already taken"}), 409
    password_hash = generate_password_hash(str(password))
    user = user_repo.create(
        username=username, password_hash=password_hash, email=email
    )
    return jsonify({"id": user["id"], "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    user = user_repo.find_by_username(username)
    if user is None or not check_password_hash(
        user["password_hash"], str(password)
    ):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user)
    return jsonify({"token": token, "username": user["username"]})


# ── Task endpoints ─────────────────────────────────────────────


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task(user):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status", "pending")
    now = datetime.utcnow().isoformat()
    row = task_repo.create(
        owner_id=user["user_id"], title=title, status=status, created_at=now
    )
    return jsonify(serialize_task(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user):
    cursor = request.args.get("cursor")
    if cursor is not None:
        try:
            cursor = int(cursor)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid cursor"}), 400

    limit = 20
    limit_raw = request.args.get("limit")
    if limit_raw is not None:
        try:
            limit = int(limit_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid limit"}), 400
        limit = max(1, min(limit, 100))

    rows = task_repo.list_for_owner_paginated(
        user["user_id"], cursor=cursor, limit=limit
    )
    has_more = len(rows) > limit
    page = rows[:limit]
    total = task_repo.count_for_owner(user["user_id"])
    next_cursor = str(page[-1]["id"]) if has_more else None
    return jsonify(
        {
            "data": [serialize_task(r) for r in page],
            "next_cursor": next_cursor,
            "total": total,
        }
    )


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user, task_id):
    row = task_repo.get_for_owner(task_id, user["user_id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(serialize_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user, task_id):
    row = task_repo.get_for_owner(task_id, user["user_id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    updated = task_repo.update_task(task_id, title, status)
    if status == "completed" and row["status"] != "completed":
        user_email = resolve_user_email(user["user_id"], user["username"])
        send_notification_email.delay(user_email, updated["title"])
    return jsonify(serialize_task(updated))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
