"""
Task management Flask API with JWT authentication.

Storage: a single flat JSON file (no database). The schema is
initialized on startup by creating the file if it does not exist.

Legacy flat-file data is migrated in place: existing tasks without an
``owner_id`` keep their data and are assigned ``owner_id: null``, and a
``users`` collection is added for JWT-authenticated accounts.

All data access goes through the repository classes in ``repositories``;
route handlers never touch the store directly.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
import os
import time
from functools import wraps

import jwt
from werkzeug.security import check_password_hash

from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded

from celery_tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATA_FILE = os.environ.get("DATA_FILE", "tasks.json")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "24"))

RATELIMIT_STORAGE_URI = os.environ.get(
    "RATELIMIT_STORAGE_URI", "redis://localhost:6379/0"
)
RATE_LIMIT_STR = os.environ.get("RATE_LIMIT", "100 per minute")

app.config["SECRET_KEY"] = SECRET_KEY


def _rate_limit_key() -> str:
    """Key rate limits per authenticated user, falling back to IP."""
    user_id = getattr(g, "user_id", None)
    if user_id is not None:
        return f"user:{user_id}"
    return f"ip:{request.remote_addr}"


limiter = Limiter(
    key_func=_rate_limit_key,
    storage_uri=RATELIMIT_STORAGE_URI,
    strategy="fixed-window",
)
limiter.init_app(app)


@app.errorhandler(RateLimitExceeded)
def _handle_rate_limit_exceeded(exc):
    limit = exc.limit
    args = [limit.key_func(), limit.scope_for(request.endpoint or "", request.method)]
    window = limiter.limiter.get_window_stats(limit.limit, *args)
    retry_after = max(0, int(window[0] + 1 - time.time()))
    response = jsonify({"error": "rate limit exceeded"})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


per_user_rate_limit = limiter.shared_limit(
    RATE_LIMIT_STR, scope="user", key_func=_rate_limit_key
)


def _current_data_file() -> str:
    return DATA_FILE


task_repository = TaskRepository(_current_data_file)
user_repository = UserRepository(_current_data_file)


def init_store():
    """Initialize the flat-file schema on startup."""
    task_repository._read_store()


# ── Auth helpers ─────────────────────────────────────────────


def verify_user(username: str, password: str) -> dict | None:
    user = user_repository.get_by_username(username)
    if user is None:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return {"id": user["id"], "username": user["username"]}


def notify_task_completed(task: dict, owner_id: int) -> None:
    """Dispatch an async email notification for a completed task.

    Sending is delegated to Celery (non-blocking): the task is queued via
    ``.delay`` and the API response is returned immediately.
    """
    email = user_repository.get_email(owner_id)
    if email is None:
        return
    send_notification_email.delay(email, task["title"])


def _generate_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != "Bearer":
            return jsonify({"error": "missing or invalid token"}), 401
        token = parts[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.PyJWTError:
            return jsonify({"error": "missing or invalid token"}), 401
        g.user_id = payload.get("sub")
        g.username = payload.get("username")
        if g.user_id is None or user_repository.get(g.user_id) is None:
            return jsonify({"error": "missing or invalid token"}), 401
        return f(*args, **kwargs)

    return wrapper


# ── Routes: auth ─────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
@per_user_rate_limit
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if password is None or not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    username = username.strip()
    try:
        user = user_repository.create(username, password)
    except ValueError:
        return jsonify({"error": "username already taken"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
@per_user_rate_limit
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "username and password are required"}), 400
    user = verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    token = _generate_token(user)
    return jsonify({"token": token, "username": user["username"], "id": user["id"]})


# ── Routes: tasks (protected) ─────────────────────────────────

@app.route("/tasks", methods=["GET"])
@require_auth
@per_user_rate_limit
def list_tasks():
    limit = request.args.get("limit", default=20, type=int)
    if limit < 1:
        limit = 20
    limit = min(limit, 100)

    cursor = None
    cursor_raw = request.args.get("cursor")
    if cursor_raw is not None and cursor_raw != "":
        try:
            cursor = int(cursor_raw)
        except ValueError:
            return jsonify({"error": "cursor must be an integer"}), 400

    page, total, start = task_repository.list_page(
        g.user_id, cursor=cursor, limit=limit
    )
    next_cursor = None
    if page and len(page) == limit and start + len(page) < total:
        next_cursor = str(page[-1]["id"])
    return jsonify({"data": page, "next_cursor": next_cursor, "total": total})


@app.route("/tasks", methods=["POST"])
@require_auth
@per_user_rate_limit
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create(title.strip(), g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
@per_user_rate_limit
def show_task(task_id: int):
    task = task_repository.get(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
@per_user_rate_limit
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    status = data.get("status")
    if title is not None and not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    previous = task_repository.get(task_id, g.user_id)
    task = task_repository.update(task_id, g.user_id, title=title, status=status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        task.get("status") == "completed"
        and (previous is None or previous.get("status") != "completed")
    ):
        notify_task_completed(task, g.user_id)
    return jsonify(task)


if __name__ == "__main__":
    init_store()
    app.run(debug=True)
