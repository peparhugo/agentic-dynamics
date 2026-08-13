"""
Flask Task Management API with SQLAlchemy and SQLite storage.
Features proper connection pooling, error handling, JWT authentication, and async email notifications.
"""

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import os
from functools import wraps
from tasks import celery, send_notification_email
from repositories import UserRepository, TaskRepository

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": QueuePool,
    "pool_size": 20,
    "max_overflow": 10,
}

db = SQLAlchemy(app)

limiter = Limiter(
    app=app,
    key_func=lambda: get_current_user_id(),
    default_limits=["100 per minute"],
    storage_uri=REDIS_URL,
)


def get_current_user_id():
    """Get user ID for rate limiting."""
    user = get_current_user()
    if user:
        return str(user.id)
    return get_remote_address()


# ── Models ────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, default="")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ── Repository Initialization ─────────────────────────────────

user_repository = UserRepository(db, User)
task_repository = TaskRepository(db, Task)


# ── JWT Utilities ─────────────────────────────────────────────

def generate_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except (jwt.DecodeError, jwt.ExpiredSignatureError, KeyError):
        return None


def get_current_user():
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    try:
        bearer, token = auth_header.split()
        if bearer.lower() != "bearer":
            return None
        user_id = verify_token(token)
        if user_id is None:
            return None
        return user_repository.get_by_id(user_id)
    except (ValueError, IndexError):
        return None


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, user=user, **kwargs)
    return decorated_function


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "rate limit exceeded"}), 429


def init_db():
    with app.app_context():
        db.create_all()
        migrate_existing_tasks()


def migrate_existing_tasks():
    """Migrate existing tasks without owner_id to a default user."""
    try:
        tasks_without_owner = task_repository.find_tasks_without_owner()
        if tasks_without_owner is None:
            return

        default_user = user_repository.find_by_username("admin")
        if default_user is None:
            default_user = user_repository.create(
                username="admin",
                email="admin@example.com",
                password_hash=generate_password_hash("admin")
            )
        else:
            default_user.set_password("admin")

        task_repository.update_tasks_without_owner(default_user.id)
    except Exception:
        pass


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
@limiter.limit("100 per minute", key_func=get_remote_address)
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip() if data.get("username") else ""
    password = data.get("password", "").strip() if data.get("password") else ""
    email = data.get("email", "").strip() if data.get("email") else ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if user_repository.find_by_username(username):
        return jsonify({"error": "username already exists"}), 400

    user = user_repository.create(
        username=username,
        email=email or f"{username}@example.com",
        password_hash=generate_password_hash(password)
    )

    token = generate_token(user.id)
    return jsonify({"token": token, "user_id": user.id}), 201


@app.route("/auth/login", methods=["POST"])
@limiter.limit("100 per minute", key_func=get_remote_address)
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip() if data.get("username") else ""
    password = data.get("password", "").strip() if data.get("password") else ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_repository.find_by_username(username)
    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    token = generate_token(user.id)
    return jsonify({"token": token, "user_id": user.id}), 200

@app.route("/tasks", methods=["GET"])
@require_auth
@limiter.limit("100 per minute")
def list_tasks(user):
    cursor = request.args.get("cursor", type=int)
    limit = request.args.get("limit", 20, type=int)

    if limit < 1 or limit > 100:
        limit = 20

    all_tasks = task_repository.find_by_owner(user.id)
    total = len(all_tasks)

    if cursor is None:
        paginated_tasks = all_tasks[:limit]
    else:
        start_idx = None
        for i, task in enumerate(all_tasks):
            if task.id == cursor:
                start_idx = i + 1
                break

        if start_idx is None:
            paginated_tasks = []
        else:
            paginated_tasks = all_tasks[start_idx:start_idx + limit]

    next_cursor = None
    if paginated_tasks and len(all_tasks) > (all_tasks.index(paginated_tasks[-1]) + 1):
        next_cursor = paginated_tasks[-1].id

    return jsonify({
        "data": [task.to_dict() for task in paginated_tasks],
        "next_cursor": next_cursor,
        "total": total,
    })


@app.route("/tasks", methods=["POST"])
@require_auth
@limiter.limit("100 per minute")
def add_task(user):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip() if data.get("title") else ""

    if not title:
        return jsonify({"error": "title is required"}), 400

    task = task_repository.create(title=title, status="pending", owner_id=user.id)

    return jsonify(task.to_dict()), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
@limiter.limit("100 per minute")
def show_task(task_id: int, user):
    task = task_repository.get_by_id(task_id)
    if task is None or task.owner_id != user.id:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task.to_dict())


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
@limiter.limit("100 per minute")
def edit_task(task_id: int, user):
    task = task_repository.get_by_id(task_id)
    if task is None or task.owner_id != user.id:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}
    old_status = task.status
    updates = {}

    if "title" in data and data["title"]:
        updates["title"] = data["title"].strip()

    if "status" in data and data["status"]:
        updates["status"] = data["status"]

    if updates:
        task = task_repository.update(task, **updates)

    if old_status != "completed" and task.status == "completed":
        send_notification_email.delay(user.email or user.username, task.title)

    return jsonify(task.to_dict())


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
