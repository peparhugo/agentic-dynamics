"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT UNIQUE NOT NULL,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER NOT NULL DEFAULT 1,"
            "  FOREIGN KEY (owner_id) REFERENCES users(id)"
            ")"
        )
        conn.commit()


# ── Auth Models ───────────────────────────────────────────────

def register_user(username: str, password: str) -> dict | tuple:
    """Register a new user. Returns user dict or (error, message) tuple."""
    if not username or not password:
        return ("validation_error", "username and password required")
    with get_db() as conn:
        try:
            password_hash = generate_password_hash(password)
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "username": username,
            }
        except sqlite3.IntegrityError:
            return ("conflict_error", "username already exists")


def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate user and return user dict if valid."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            return {"id": row["id"], "username": row["username"]}
    return None


def create_jwt_token(user_id: int) -> str:
    """Create a JWT token for the user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_jwt_token(token: str) -> dict | None:
    """Verify and decode JWT token. Returns payload if valid."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
        return None


def get_current_user() -> int | None:
    """Extract user_id from Authorization header. Returns user_id or None."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    payload = verify_jwt_token(token)
    return payload["user_id"] if payload else None


def require_auth(f):
    """Decorator to require valid JWT token."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_current_user()
        if user_id is None:
            return jsonify({"error": "missing or invalid token"}), 401
        return f(*args, **kwargs)
    return decorated_function


# ── Models ────────────────────────────────────────────────────

def create_task(title: str, owner_id: int) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }


def get_tasks(owner_id: int):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        return dict(row) if row else None


def is_valid_status(status: str) -> bool:
    return status in ("pending", "done")


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None | tuple:
    task = get_task(task_id, owner_id)
    if task is None:
        return None
    if status is not None and not is_valid_status(status):
        return ("invalid_status", status)
    with get_db() as conn:
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
    return get_task(task_id, owner_id)


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    result = register_user(username, password)
    if isinstance(result, tuple):
        error_type, message = result
        if error_type == "conflict_error":
            return jsonify({"error": message}), 409
        return jsonify({"error": message}), 400
    return jsonify(result), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    user = authenticate_user(username, password)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401
    token = create_jwt_token(user["id"])
    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    user_id = get_current_user()
    return jsonify(get_tasks(user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    user_id = get_current_user()
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    user_id = get_current_user()
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    user_id = get_current_user()
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if isinstance(task, tuple) and task[0] == "invalid_status":
        return jsonify({"error": f"invalid status: {task[1]}"}), 422
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
