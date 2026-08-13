"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import check_password_hash
import redis
import sqlite3
import os
import jwt

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXP_DELTA = timedelta(hours=24)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT = os.environ.get("RATE_LIMIT", "100 per minute")
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100


def _storage_options():
    # Lets the test suite point flask-limiter at an in-process fake Redis
    # server instead of a real one, without changing any production code path.
    if os.environ.get("FAKE_REDIS") == "1":
        import fakeredis

        pool = redis.ConnectionPool(connection_class=fakeredis.FakeRedisConnection)
        return {"connection_pool": pool}
    return {}


def rate_limit_key():
    """Key by authenticated user when possible, otherwise by IP (e.g. auth endpoints)."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
                return f"user:{payload.get('user_id')}"
            except jwt.InvalidTokenError:
                pass
    return f"ip:{get_remote_address()}"


limiter = Limiter(
    key_func=rate_limit_key,
    app=app,
    storage_uri=REDIS_URL,
    storage_options=_storage_options(),
    # application_limits (not default_limits) gives one shared budget per key
    # across every endpoint, rather than a separate 100/minute bucket per route.
    application_limits=[RATE_LIMIT],
    headers_enabled=True,
)


@app.errorhandler(429)
def handle_rate_limit_exceeded(e):
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    return response


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


user_repository = UserRepository(get_db)
task_repository = TaskRepository(get_db)


def init_db():
    with get_db() as conn:
        user_repository.create_schema(conn)
        task_repository.create_schema(conn)
        task_repository.migrate_schema(conn)


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    import re
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated

# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


def generate_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + JWT_EXP_DELTA,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def fetch_task(task_id: int, owner_id: int) -> dict | None:
    """Alias for task_repository.get — used by legacy clients."""
    return task_repository.get(task_id, owner_id)


# ── Auth ─────────────────────────────────────────────────────


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        token = auth_header[len("Bearer "):].strip()
        if not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid token"}), 401
        user = user_repository.get_by_id(payload.get("user_id"))
        if user is None:
            return jsonify({"error": "invalid token"}), 401
        request.user_id = user["id"]
        return f(*args, **kwargs)
    return decorated


# ── Routes ─────────────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repository.get_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = user_repository.create_user(username, password)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repository.get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    raw_cursor = request.args.get("cursor")
    raw_limit = request.args.get("limit")
    try:
        cursor = int(raw_cursor) if raw_cursor is not None else None
    except ValueError:
        return jsonify({"error": "cursor must be an integer"}), 400
    try:
        limit = int(raw_limit) if raw_limit is not None else DEFAULT_PAGE_LIMIT
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400
    limit = max(1, min(limit, MAX_PAGE_LIMIT))
    result = task_repository.list_for_owner(request.user_id, cursor=cursor, limit=limit)
    return jsonify(result)


@app.route("/tasks", methods=["POST"])
@token_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create(title, request.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def show_task(task_id: int):
    task = task_repository.get(task_id, request.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    previous = task_repository.get(task_id, request.user_id)
    task = task_repository.update(
        task_id,
        request.user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if task["status"] == "completed" and previous["status"] != "completed":
        owner = user_repository.get_by_id(task["owner_id"])
        if owner is not None:
            send_notification_email.delay(owner["username"], task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
