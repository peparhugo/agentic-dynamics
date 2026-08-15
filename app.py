"""Minimal Flask Task Management API backed by SQLite, with JWT authentication."""

from functools import wraps
from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import jwt

from notifications import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-me-please-32-bytes-min")
JWT_ALGORITHM = "HS256"
JWT_EXP_MINUTES = 60


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        _migrate_add_owner_id(conn)
        _migrate_add_email(conn)


def _migrate_add_owner_id(conn: sqlite3.Connection) -> None:
    """Add the tasks.owner_id column if it doesn't already exist.

    Existing rows (created before auth existed) are left with owner_id = NULL
    rather than being deleted or assigned to a guessed user.
    """
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(tasks)")]
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def _migrate_add_email(conn: sqlite3.Connection) -> None:
    """Add the users.email column if it doesn't already exist.

    Existing users (registered before email existed) are left with email = NULL;
    notification sending falls back to a derived address for them.
    """
    columns = [row["name"] for row in conn.execute("PRAGMA table_info(users)")]
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


# ── User model ────────────────────────────────────────────────


def create_user(username: str, password: str, email: str | None = None) -> dict:
    password_hash = generate_password_hash(password)
    email = email or f"{username}@example.com"
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        conn.commit()
        return {"id": cur.lastrowid, "username": username, "email": email}


def get_user_email(user: dict) -> str:
    """Return the user's notification email, deriving one for legacy users without it."""
    return user.get("email") or f"{user['username']}@example.com"


def get_user_by_username(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ── Task model ────────────────────────────────────────────────


def create_task(title: str, owner_id: int) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        next_id = conn.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM tasks"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) VALUES (?, ?, 'pending', ?, ?)",
            (next_id, title, now, owner_id),
        )
        conn.commit()
        return {
            "id": next_id,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": owner_id,
        }


def get_tasks(owner_id: int) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
        return dict(row) if row else None


def update_task(
    task_id: int, owner_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    task = get_task(task_id, owner_id)
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
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                params,
            )
            conn.commit()
    return get_task(task_id, owner_id)


# ── JWT helpers ───────────────────────────────────────────────


def generate_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[len("Bearer ") :].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, ValueError, KeyError):
            return jsonify({"error": "missing or invalid token"}), 401
        user = get_user_by_id(user_id)
        if user is None:
            return jsonify({"error": "missing or invalid token"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


# ── Auth routes ───────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400
    username = username.strip()
    if get_user_by_username(username) is not None:
        return jsonify({"error": "username already taken"}), 409
    user = create_user(username, password, email.strip() if email else None)
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401
    user = get_user_by_username(username.strip())
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = generate_token(user["id"])
    return jsonify({"token": token})


# ── Task routes ───────────────────────────────────────────────


@app.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    return jsonify(get_tasks(g.current_user["id"]))


@app.route("/tasks", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = create_task(title.strip(), g.current_user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def show_task(task_id: int):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    existing = get_task(task_id, g.current_user["id"])
    if existing is None:
        return jsonify({"error": "task not found"}), 404
    task = update_task(
        task_id,
        g.current_user["id"],
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if existing["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(get_user_email(g.current_user), task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
