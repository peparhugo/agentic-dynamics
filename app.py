"""
Task Management Flask API

A simple REST API for managing tasks with SQLite persistence.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from celery_tasks import celery, send_notification_email

app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")


def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        conn.commit()


def dict_from_row(row):
    """Convert sqlite3.Row to dict."""
    return dict(row) if row else None


def generate_token(user_id):
    """Generate JWT token for user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token):
    """Verify JWT token and return user_id."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except jwt.InvalidTokenError:
        return None


def get_user_email(user_id):
    """Get user email by user_id."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT email FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
    return dict(row)["email"] if row else None


def auth_required(f):
    """Decorator to protect endpoints with JWT authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401

        token = auth_header[7:]
        user_id = verify_token(token)

        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401

        return f(user_id, *args, **kwargs)

    return decorated_function


@app.route("/auth/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()

    if not username:
        return jsonify({"error": "username is required"}), 400

    if not password:
        return jsonify({"error": "password is required"}), 400

    password_hash = generate_password_hash(password)

    with get_db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email)
            )
            conn.commit()
            user_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409

    token = generate_token(user_id)
    return jsonify({
        "user_id": user_id,
        "username": username,
        "token": token
    }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    """Login user and return JWT token."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401

    user_id = row["id"]
    token = generate_token(user_id)
    return jsonify({
        "user_id": user_id,
        "username": username,
        "token": token
    }), 200


@app.route("/tasks", methods=["POST"])
@auth_required
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
            (title, "pending", now, user_id)
        )
        conn.commit()
        task_id = cursor.lastrowid

    return jsonify({
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": now,
        "owner_id": user_id
    }), 201


@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks(user_id):
    """List all tasks for the authenticated user ordered by created_at descending."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def get_task(user_id, task_id):
    """Get a single task by ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id)
        ).fetchone()

    if row is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def update_task(user_id, task_id):
    """Update task title and/or status."""
    data = request.get_json(silent=True) or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id)
        ).fetchone()

        if row is None:
            return jsonify({"error": "task not found"}), 404

        task = dict(row)
        old_status = task["status"]

        # Update title only if provided and not empty
        if "title" in data:
            stripped_title = data.get("title", "").strip()
            if stripped_title:
                title = stripped_title
            else:
                title = task["title"]
        else:
            title = task["title"]

        status = data.get("status", task["status"])

        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id)
        )
        conn.commit()

        task["title"] = title
        task["status"] = status

    # Trigger async email notification if status changed to completed
    if old_status != "completed" and status == "completed":
        user_email = get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, title)

    return jsonify(task)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
