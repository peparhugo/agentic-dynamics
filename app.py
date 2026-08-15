"""
Flask Todo API with JWT authentication.

A single-file Flask app with clean structure: models, routes, error handling.
Each user authenticates with a username/password and sees only their own tasks.
"""

from flask import Flask, request, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "dev-secret-change-me-0123456789abcdef"
)

jwt = JWTManager(app)


@jwt.invalid_token_loader
def _invalid_token_callback(reason):
    return jsonify({"error": "invalid token"}), 401


@jwt.expired_token_loader
def _expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"error": "token has expired"}), 401

DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _tasks_has_owner_id(conn) -> bool:
    rows = conn.execute("PRAGMA table_info(tasks)").fetchall()
    return any(r["name"] == "owner_id" for r in rows)


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
        # Migration: add owner_id to a pre-existing tasks table without
        # destroying existing rows.
        if not _tasks_has_owner_id(conn):
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


# ── Models ────────────────────────────────────────────────────


def create_user(username: str, password: str) -> dict | None:
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username}
        except sqlite3.IntegrityError:
            return None


def find_user(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def verify_user(username: str, password: str) -> dict | None:
    user = find_user(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return None
    return user


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


def fetch_task(task_id: int, owner_id: int) -> dict | None:
    """Alias for get_task — used by legacy clients."""
    return get_task(task_id, owner_id)


def update_task(
    task_id: int,
    owner_id: int,
    title: str | None = None,
    status: str | None = None,
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


# ── Auth helpers ──────────────────────────────────────────────


def current_user_id() -> int:
    username = get_jwt_identity()
    user = find_user(username)
    return user["id"] if user else None


# ── Routes ─────────────────────────────────────────────────────


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username:
        return jsonify({"error": "username is required"}), 400
    if not password:
        return jsonify({"error": "password is required"}), 400
    user = create_user(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401
    token = create_access_token(identity=username)
    return jsonify({"access_token": token}), 200


@app.route("/tasks", methods=["GET"])
@jwt_required()
def list_tasks():
    return jsonify(get_tasks(current_user_id()))


@app.route("/tasks", methods=["POST"])
@jwt_required()
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, current_user_id())
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@jwt_required()
def show_task(task_id: int):
    task = get_task(task_id, current_user_id())
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@jwt_required()
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        current_user_id(),
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
