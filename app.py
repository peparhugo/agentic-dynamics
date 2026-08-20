"""
Task management API with JWT authentication.

A single-file Flask app with clean structure: models, routes, error handling.
Users register/login to receive a JWT, and all /tasks/* endpoints require it.
"""

from datetime import datetime, timezone
from functools import wraps
import os
import sqlite3

from flask import Flask, g, jsonify, request
import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from tasks import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-secret-key-change-me-0123456789abcdef"
)
JWT_ALGORITHM = "HS256"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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
            "  owner_id INTEGER"
            ")"
        )
        conn.commit()


def migrate():
    """Add owner_id to pre-existing task tables without breaking existing data."""
    with get_db() as conn:
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            conn.commit()


# ── Auth helpers ──────────────────────────────────────────────

def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "iat": datetime.now(timezone.utc)}
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=JWT_ALGORITHM)


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth[len("Bearer "):].strip()
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[JWT_ALGORITHM])
        except jwt.InvalidTokenError:
            return jsonify({"error": "missing or invalid token"}), 401
        g.user_id = int(payload["sub"])
        return f(*args, **kwargs)

    return wrapper


# ── Models ────────────────────────────────────────────────────

def create_user(username: str, password: str) -> dict:
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "username": username}


def get_user_by_username(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_email(user_id: int) -> str | None:
    """Resolve a user's notification email address from their account."""
    with get_db() as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        return f"{row['username']}@example.com" if row else None


def create_task(owner_id: int, title: str) -> dict:
    with get_db() as conn:
        now = datetime.now(timezone.utc).isoformat()
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
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(owner_id: int, task_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
        return dict(row) if row else None


def update_task(
    owner_id: int,
    task_id: int,
    title: str | None = None,
    status: str | None = None,
) -> dict | None:
    task = get_task(owner_id, task_id)
    if task is None:
        return None
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
            params.append(owner_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params
            )
            conn.commit()
    return get_task(owner_id, task_id)


# ── Auth routes ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if get_user_by_username(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    user = create_user(username, password)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"])
    return jsonify({"token": token, "user_id": user["id"]})


# ── Task routes ───────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    return jsonify(get_tasks(g.user_id))


@app.route("/tasks", methods=["POST"])
@token_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(g.user_id, title)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def show_task(task_id: int):
    task = get_task(g.user_id, task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    previous = get_task(g.user_id, task_id)
    if previous is None:
        return jsonify({"error": "task not found"}), 404
    task = update_task(
        g.user_id,
        task_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task["status"] == "completed" and previous["status"] != "completed":
        user_email = get_user_email(g.user_id)
        if user_email is not None:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    migrate()
    app.run(debug=True)
