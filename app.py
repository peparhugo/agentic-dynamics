import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
import jwt
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address

from repositories import TaskRepository, UserRepository, storage_lock
from tasks import send_notification_email

app = Flask(__name__)
app.config["STORAGE_FILE"] = os.environ.get("TASKS_DB", "tasks.json")
app.config["USERS_FILE"] = os.environ.get("USERS_DB", "users.json")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["JWT_ALGORITHM"] = "HS256"
RATE_LIMIT_STORAGE_URI = os.environ.get("RATE_LIMIT_STORAGE_URI", "redis://localhost:6379")
app.config["RATELIMIT_STORAGE_URI"] = RATE_LIMIT_STORAGE_URI
app.config["RATELIMIT_HEADERS_ENABLED"] = True

TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL", "3600"))

task_repository = TaskRepository(lambda: app.config["STORAGE_FILE"])
user_repository = UserRepository(lambda: app.config["USERS_FILE"])


def init_storage():
    task_repository.ensure_exists()
    user_repository.ensure_exists()
    migrate_storage()


def migrate_storage():
    with storage_lock:
        tasks = task_repository.all()
        legacy_ids = [t["id"] for t in tasks if t.get("owner_id") is None]
        if not legacy_ids:
            return
        legacy_user = user_repository.find_by_username("legacy")
        if legacy_user is None:
            legacy_user = user_repository.create(
                username="legacy",
                password_hash=hash_password(secrets.token_hex(16)),
                created_at=datetime.utcnow().isoformat(),
            )
        for task in tasks:
            if task["id"] in legacy_ids:
                task["owner_id"] = legacy_user["id"]
        task_repository.save_all(tasks)


def _user_email(user):
    email = (user.get("email") or "").strip()
    if email:
        return email
    return f"{user.get('username', 'user')}@example.com"


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id, username):
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])


def get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, app.config["SECRET_KEY"], algorithms=[app.config["JWT_ALGORITHM"]]
        )
    except jwt.InvalidTokenError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    return user_repository.get(user_id)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        return f(user, *args, **kwargs)

    return decorated


def rate_limit_key():
    user = get_current_user()
    if user is not None:
        return f"user:{user['id']}"
    return get_remote_address()


def default_rate_limit():
    return app.config.get("RATELIMIT_DEFAULT_LIMIT", "100 per minute")


limiter = Limiter(
    key_func=rate_limit_key,
    default_limits=[default_rate_limit],
    headers_enabled=True,
    storage_uri=RATE_LIMIT_STORAGE_URI,
)


@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(_exc):
    return jsonify({"error": "rate limit exceeded"}), 429


limiter.init_app(app)


@app.route("/auth/register", methods=["POST"])
def register():
    init_storage()
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repository.find_by_username(username) is not None:
        return jsonify({"error": "username already taken"}), 409
    email = (data.get("email") or "").strip() or None
    user = user_repository.create(
        username=username,
        password_hash=hash_password(password),
        email=email,
        created_at=datetime.utcnow().isoformat(),
    )
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    init_storage()
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = user_repository.find_by_username(username)
    if user is None or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"], user["username"])
    return jsonify({"token": token, "username": user["username"]})


def trigger_completion_notification(task):
    owner = user_repository.get(task.get("owner_id"))
    if owner is None:
        return
    email = _user_email(owner)
    send_notification_email.delay(email, task.get("title", ""))


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task(user):
    init_storage()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repository.create(
        owner_id=user["id"],
        title=title,
        status="pending",
        created_at=datetime.utcnow().isoformat(),
    )
    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user):
    init_storage()
    try:
        limit = int(request.args.get("limit", 20))
    except (TypeError, ValueError):
        limit = 20
    if limit < 1:
        limit = 20
    limit = min(limit, 100)

    cursor_raw = request.args.get("cursor")
    cursor = None
    if cursor_raw is not None:
        try:
            cursor = int(cursor_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid cursor"}), 400

    tasks = task_repository.find_by_owner(user["id"])
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    total = len(tasks)

    start = 0
    if cursor is not None:
        cursor_index = next(
            (i for i, task in enumerate(tasks) if task.get("id") == cursor), None
        )
        if cursor_index is None:
            return jsonify({"error": "invalid cursor"}), 400
        start = cursor_index + 1

    page = tasks[start : start + limit]
    next_cursor = None
    if start + limit < total:
        next_cursor = str(page[-1]["id"])
    return jsonify({"data": page, "next_cursor": next_cursor, "total": total})


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user, task_id):
    init_storage()
    task = task_repository.get(task_id)
    if task is None or task.get("owner_id") != user["id"]:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user, task_id):
    init_storage()
    data = request.get_json(silent=True) or {}
    task = task_repository.get(task_id)
    if task is None or task.get("owner_id") != user["id"]:
        return jsonify({"error": "task not found"}), 404
    was_completed = task.get("status") == "completed"
    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        task["title"] = title
    if "status" in data:
        status = (data.get("status") or "").strip()
        if not status:
            return jsonify({"error": "status is required"}), 400
        task["status"] = status
    task_repository.save(task)
    if not was_completed and task.get("status") == "completed":
        trigger_completion_notification(task)
    return jsonify(task)


if __name__ == "__main__":
    init_storage()
    app.run(debug=True)
