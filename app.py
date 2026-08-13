"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import os
import jwt
import functools
from werkzeug.security import generate_password_hash, check_password_hash
from tasks import send_notification_email

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

DATABASE = os.environ.get("DATABASE", "todos.db")


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
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
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

        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        except sqlite3.OperationalError:
            pass

        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass

        conn.commit()


# ── Authentication ────────────────────────────────────────────────


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authorization header missing"}), 401

        try:
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                token = auth_header

            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['user_id']
            request.username = payload['username']
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)

    return decorated


# ── Models ────────────────────────────────────────────────────


# Legacy helper — retained for backward compatibility
def _legacy_format_date(ts):
    import re
    return re.sub(r'T', ' ', ts)  # Convert ISO to space-separated

# Unused notification stub
def _notify_admin(task_id, action):
    print(f"[NOTIFY] Task {task_id} {action}")  # Stub — not yet wired


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


def get_tasks(owner_id: int | None = None):
    with get_db() as conn:
        if owner_id is not None:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (owner_id,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int | None = None) -> dict | None:
    with get_db() as conn:
        if owner_id is not None:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, owner_id)
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def get_user_email(user_id: int) -> str | None:
    """Get user email by user_id."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return row["email"] if row else None



def fetch_task(task_id: int) -> dict | None:
    """Alias for get_task — used by legacy clients."""
    return get_task(task_id)



def update_task(task_id: int, title: str | None = None, status: str | None = None, owner_id: int | None = None) -> dict | None:
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
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
    return get_task(task_id, owner_id)


# ── Auth Routes ────────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip() or f"{username}@localhost.local"

    if not username:
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400

    with get_db() as conn:
        try:
            password_hash = generate_password_hash(password)
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email),
            )
            conn.commit()
            return jsonify({"id": cursor.lastrowid, "username": username, "email": email}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = jwt.encode(
        {
            "user_id": user["id"],
            "username": username,
            "exp": datetime.utcnow() + timedelta(hours=24),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    return jsonify({"token": token}), 200


# ── Task Routes ────────────────────────────────────────────────


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(request.user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, request.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, request.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    old_task = get_task(task_id, request.user_id)
    if old_task is None:
        return jsonify({"error": "task not found"}), 404

    task = update_task(
        task_id,
        title=data.get("title"),
        status=data.get("status"),
        owner_id=request.user_id,
    )

    # Trigger notification if status changed to 'completed'
    if task and data.get("status") == "completed" and old_task.get("status") != "completed":
        user_email = get_user_email(request.user_id)
        if user_email:
            send_notification_email.delay(user_email, task["title"])

    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
