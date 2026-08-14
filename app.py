"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from functools import wraps
from werkzeug.security import check_password_hash
import os
import jwt

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from repositories import get_db, UserRepository, TaskRepository
from tasks import send_notification_email

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

user_repo = UserRepository()
task_repo = TaskRepository()


# ── Rate limiting ──────────────────────────────────────────────

def rate_limit_key() -> str:
    """Identify a caller for rate limiting: authenticated user or IP."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):]
        try:
            payload = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.PyJWTError:
            pass
        else:
            user_id = payload.get("sub")
            if user_id is not None:
                return f"user:{user_id}"
    return f"ip:{get_remote_address()}"


def app_rate_limit() -> str:
    """Rate limit applied to every endpoint, per authenticated user."""
    return os.environ.get("RATELIMIT_APP_LIMIT", "100 per minute")


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=os.environ.get(
        "RATELIMIT_STORAGE_URI", "redis://localhost:6379"
    ),
    application_limits=[app_rate_limit],
    headers_enabled=True,
)
limiter.init_app(app)


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
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in cols:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
        conn.commit()


# ── Auth helpers ──────────────────────────────────────────────

def get_authenticated_user() -> dict | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    return user_repo.get_by_id(user_id)


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_authenticated_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user = user
        return f(*args, **kwargs)
    return wrapper


# ── Notifications ──────────────────────────────────────────────

def dispatch_completion_email(user_email: str, task_title: str) -> None:
    """Queue a notification email asynchronously via Celery."""
    send_notification_email.delay(user_email, task_title)


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if user_repo.get_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = user_repo.create_user(username, password)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = user_repo.get_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode(
        {"sub": user["id"]}, app.config["SECRET_KEY"], algorithm="HS256"
    )
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    cursor_raw = request.args.get("cursor")
    cursor = None
    if cursor_raw is not None and cursor_raw != "":
        try:
            cursor = int(cursor_raw)
        except ValueError:
            return jsonify({"error": "invalid cursor"}), 400

    limit_raw = request.args.get("limit", "20")
    try:
        limit = int(limit_raw)
    except ValueError:
        return jsonify({"error": "invalid limit"}), 400
    limit = max(1, min(limit, 100))

    items, next_cursor = task_repo.get_tasks_page(
        owner_id=g.user["id"], cursor=cursor, limit=limit
    )
    total = task_repo.count_tasks_by_owner(g.user["id"])
    return jsonify(
        {
            "data": items,
            "next_cursor": str(next_cursor) if next_cursor is not None else None,
            "total": total,
        }
    )


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create_task(title, owner_id=g.user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = task_repo.get_task(task_id, owner_id=g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    existing = task_repo.get_task(task_id, owner_id=g.user["id"])
    task = task_repo.update_task(
        task_id,
        owner_id=g.user["id"],
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if (
        existing is not None
        and existing["status"] != "completed"
        and task["status"] == "completed"
    ):
        dispatch_completion_email(g.user["username"], task["title"])
    return jsonify(task)


init_db()

if __name__ == "__main__":
    app.run(debug=True)
