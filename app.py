"""
Flask Task Management API

A simple task management API with SQLite persistence and JWT authentication.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from tasks_celery import celery_app, send_notification_email

app = Flask(__name__)
app.config["CELERY_BROKER_URL"] = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
app.config["CELERY_RESULT_BACKEND"] = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app.conf.update(app.config)

class ContextTask(celery_app.Task):
    def __call__(self, *args, **kwargs):
        with app.app_context():
            return self.run(*args, **kwargs)

celery_app.Task = ContextTask

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


# ── Database ────────────────────────────────────────────────────

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
                password_hash TEXT NOT NULL,
                email TEXT
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users (id)
            );
        """)


# ── Authentication Helpers ─────────────────────────────────────

def get_jwt_token(user_id):
    """Generate a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_jwt_token(token):
    """Verify and decode a JWT token. Returns user_id or None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
        return None


def require_auth(f):
    """Decorator to require JWT authentication on an endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401

        token = auth_header[7:]
        user_id = verify_jwt_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401

        return f(user_id, *args, **kwargs)
    return decorated_function


# ── Helper Functions ────────────────────────────────────────────

def get_user_email(user_id):
    """Get the email address for a user, return None if not found."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return row["email"] if row else None


def task_to_dict(row):
    """Convert a database row to a dictionary."""
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


# ── Authentication Endpoints ────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip() if "email" in data else None

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    password_hash = generate_password_hash(password)

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            conn.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 400

    token = get_jwt_token(user_id)
    return jsonify({"token": token}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    """Log in a user and return a JWT token."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    token = get_jwt_token(user["id"])
    return jsonify({"token": token}), 200


# ── Task Endpoints ──────────────────────────────────────────────

@app.route("/tasks", methods=["POST"])
@require_auth
def create_task(user_id):
    """Create a new task."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, "pending", now, user_id),
        )
        conn.commit()
        task_id = cursor.lastrowid

    return jsonify({
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": now,
    }), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user_id):
    """List all tasks for the authenticated user ordered by created_at descending."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()

    return jsonify([task_to_dict(row) for row in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user_id, task_id):
    """Get a single task by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()

    if row is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user_id, task_id):
    """Update a task's title and/or status."""
    data = request.get_json(silent=True) or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()

        if row is None:
            return jsonify({"error": "task not found"}), 404

        title = data.get("title", row["title"]).strip() if "title" in data else row["title"]
        status = data.get("status", row["status"]) if "status" in data else row["status"]

        if "title" in data and not title:
            return jsonify({"error": "title cannot be empty"}), 400

        old_status = row["status"]
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        conn.commit()

    if status == "completed" and old_status != "completed":
        user_email = get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, title)

    return jsonify({
        "id": task_id,
        "title": title,
        "status": status,
        "created_at": row["created_at"],
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
