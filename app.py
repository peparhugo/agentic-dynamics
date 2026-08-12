from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import secrets

import jwt
from werkzeug.security import generate_password_hash, check_password_hash

from celery_app import send_notification_email

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATABASE = os.environ.get("DATABASE", "tasks.db")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "3600"))


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
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)
        migrate_tasks_owner_id(conn)
        migrate_users_email(conn)


def migrate_tasks_owner_id(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def migrate_users_email(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        conn.commit()


def resolve_user_email(user_id, fallback):
    with get_db() as conn:
        row = conn.execute(
            "SELECT email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    email = row["email"] if row is not None else None
    return email or fallback


def serialize_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def get_task_or_404(task_id, owner_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
    return row


# ── Auth utilities ─────────────────────────────────────────────


def create_token(user):
    payload = {
        "user_id": user["id"],
        "username": user["username"],
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=TOKEN_TTL),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def get_user_from_token(token):
    try:
        payload = jwt.decode(
            token, app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    return payload


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth.split(" ", 1)[1].strip()
        if not token:
            return jsonify({"error": "missing or invalid token"}), 401
        user = get_user_from_token(token)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        return f(user, *args, **kwargs)
    return decorated


# ── Auth endpoints ─────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    email = str(data.get("email", "")).strip() or None
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing is not None:
            return jsonify({"error": "username already taken"}), 409
        password_hash = generate_password_hash(str(password))
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        conn.commit()
        user_id = cursor.lastrowid
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not check_password_hash(
        user["password_hash"], str(password)
    ):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user)
    return jsonify({"token": token, "username": user["username"]})


# ── Task endpoints ─────────────────────────────────────────────


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task(user):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status", "pending")
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (owner_id, title, status, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user["user_id"], title, status, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(serialize_task(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (user["user_id"],),
        ).fetchall()
    return jsonify([serialize_task(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user, task_id):
    row = get_task_or_404(task_id, user["user_id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(serialize_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user, task_id):
    row = get_task_or_404(task_id, user["user_id"])
    if row is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    title = data.get("title", row["title"])
    status = data.get("status", row["status"])
    with get_db() as conn:
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title, status, task_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    if status == "completed" and row["status"] != "completed":
        user_email = resolve_user_email(user["user_id"], user["username"])
        send_notification_email.delay(user_email, updated["title"])
    return jsonify(serialize_task(updated))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
