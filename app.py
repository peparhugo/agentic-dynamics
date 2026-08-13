"""
Flask Task Management API with repository pattern for data access.
Uses JSON files for persistence via repository classes.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from tasks import send_notification_email
from repositories import TaskRepository, UserRepository
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["JWT_ALGORITHM"] = "HS256"
app.config["JWT_EXPIRATION_HOURS"] = 24

DATA_DIR = os.environ.get("DATA_DIR", "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# Initialize repositories
_task_repository = None
_user_repository = None


def get_task_repository():
    """Get or create the task repository."""
    global _task_repository
    if _task_repository is None:
        _task_repository = TaskRepository(TASKS_FILE)
    return _task_repository


def get_user_repository():
    """Get or create the user repository."""
    global _user_repository
    if _user_repository is None:
        _user_repository = UserRepository(USERS_FILE)
    return _user_repository


def reset_repositories():
    """Reset repository instances. Used for testing."""
    global _task_repository, _user_repository
    _task_repository = None
    _user_repository = None


# ── Authentication ─────────────────────────────────────────────

def generate_token(user_id):
    """Generate a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"])
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])


def verify_token(token):
    """Verify a JWT token and return the user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[app.config["JWT_ALGORITHM"]])
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_rate_limit_key():
    """Get rate limit key: user_id if authenticated, IP address otherwise."""
    auth_header = request.headers.get("Authorization")
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0] == "Bearer":
            token = parts[1]
            try:
                user_id = verify_token(token)
                if user_id is not None:
                    return f"user:{user_id}"
            except Exception:
                pass
    return get_remote_address()


# Rate limiter setup - now safe to initialize with verify_token defined
limiter = Limiter(
    app=app,
    key_func=get_rate_limit_key,
    default_limits=["100 per minute"],
    storage_uri=os.environ.get("REDIS_URL")
)


def token_required(f):
    """Decorator to require a valid JWT token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]

        if not token:
            return jsonify({"error": "missing or invalid authorization header"}), 401

        user_id = verify_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401

        return f(user_id, *args, **kwargs)

    return decorated


# ── Initialization & Migrations ──────────────────────────────────

def migrate_tasks_add_owner():
    """Add owner_id to existing tasks that don't have it."""
    task_repo = get_task_repository()
    user_repo = get_user_repository()

    all_users = user_repo.get_all()
    if all_users:
        default_owner_id = all_users[0]["id"]
        all_tasks = task_repo.get_all()
        modified = False
        for task in all_tasks:
            if "owner_id" not in task:
                task["owner_id"] = default_owner_id
                modified = True
        if modified:
            for task in all_tasks:
                task_repo.save(task)


def migrate_users_add_email():
    """Add email to existing users that don't have it."""
    user_repo = get_user_repository()
    user_repo.migrate_add_emails()


# ── Endpoints ───────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
@limiter.limit("100 per minute")
def register():
    """Register a new user. Requires 'username', 'password', and 'email' in JSON body."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()

    if not username or not password or not email:
        return jsonify({"error": "username, password, and email are required"}), 400

    user_repo = get_user_repository()

    if user_repo.username_exists(username):
        return jsonify({"error": "username already exists"}), 409

    password_hash = generate_password_hash(password)
    new_user = user_repo.create(username, email, password_hash)

    return jsonify({"id": new_user["id"], "username": new_user["username"], "email": new_user["email"]}), 201


@app.route("/auth/login", methods=["POST"])
@limiter.limit("100 per minute")
def login():
    """Login a user. Requires 'username' and 'password' in JSON body. Returns JWT token."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user_repo = get_user_repository()
    user = user_repo.get_by_username(username)

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401

    token = generate_token(user["id"])
    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["POST"])
@limiter.limit("100 per minute")
@token_required
def create_task(user_id):
    """Create a new task. Requires 'title' in JSON body and valid JWT."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    task_repo = get_task_repository()
    new_task = task_repo.create(title, user_id)

    return jsonify(new_task), 201


@app.route("/tasks", methods=["GET"])
@limiter.limit("100 per minute")
@token_required
def list_tasks(user_id):
    """List tasks with cursor-based pagination.

    Query params:
    - cursor: ID of last item from previous page (optional)
    - limit: Number of items per page (default=20, max=100)

    Returns: {data: [...], next_cursor: str|null, total: int}
    """
    task_repo = get_task_repository()
    user_tasks = task_repo.get_by_owner_id(user_id)
    sorted_tasks = sorted(user_tasks, key=lambda t: t["id"], reverse=True)

    # Get pagination params
    cursor = request.args.get("cursor", type=int)
    limit = request.args.get("limit", default=20, type=int)

    # Validate limit
    if limit <= 0:
        limit = 20
    if limit > 100:
        limit = 100

    # Find starting position based on cursor
    start_idx = 0
    if cursor is not None:
        for i, task in enumerate(sorted_tasks):
            if task["id"] == cursor:
                start_idx = i + 1
                break

    # Get the page of tasks
    page_tasks = sorted_tasks[start_idx : start_idx + limit]

    # Determine next cursor
    next_cursor = None
    if start_idx + limit < len(sorted_tasks) and page_tasks:
        next_cursor = page_tasks[-1]["id"]

    return jsonify({
        "data": page_tasks,
        "next_cursor": next_cursor,
        "total": len(sorted_tasks)
    }), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
@limiter.limit("100 per minute")
@token_required
def get_task(user_id, task_id):
    """Get a single task by ID. User can only access their own tasks."""
    task_repo = get_task_repository()
    task = task_repo.get_by_id(task_id)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.get("owner_id") != user_id:
        return jsonify({"error": "unauthorized"}), 403

    return jsonify(task), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@limiter.limit("100 per minute")
@token_required
def update_task(user_id, task_id):
    """Update a task's title and/or status. User can only update their own tasks."""
    data = request.get_json(silent=True) or {}
    task_repo = get_task_repository()
    user_repo = get_user_repository()

    task = task_repo.get_by_id(task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.get("owner_id") != user_id:
        return jsonify({"error": "unauthorized"}), 403

    old_status = task.get("status")

    if "title" in data:
        title = data["title"]
        if isinstance(title, str):
            title = title.strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        task["title"] = title

    if "status" in data:
        task["status"] = data["status"]

    task_repo.save(task)

    if "status" in data and data["status"] == "completed" and old_status != "completed":
        user = user_repo.get_by_id(user_id)
        if user:
            send_notification_email.delay(user["email"], task["title"])

    return jsonify(task), 200


@app.route("/health", methods=["GET"])
@limiter.limit("100 per minute")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors."""
    return jsonify({"error": "rate limit exceeded"}), 429


if __name__ == "__main__":
    migrate_tasks_add_owner()
    migrate_users_add_email()
    app.run(debug=True)
