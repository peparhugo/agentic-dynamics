"""Flask API for task management, backed by SQLite.

SQLite's INTEGER PRIMARY KEY without AUTOINCREMENT can still reuse ids after
deletes, so task ids are assigned manually from a counter persisted in a
dedicated `counters` table rather than relying on SQLite's rowid behavior.

Endpoints under /tasks require a JWT bearer token obtained via /auth/login.
Each task is scoped to the user that created it (Task.owner_id).
"""

import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.db")

JWT_ALGORITHM = "HS256"
JWT_EXP_SECONDS = 3600
MIN_PASSWORD_LENGTH = 6


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS counters (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            )
            """
        )
        conn.execute("INSERT OR IGNORE INTO counters (name, value) VALUES ('task_id', 1)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # Migration: databases created before auth existed won't have an
        # owner_id column on tasks. Add it in place so pre-existing rows are
        # preserved (they end up with owner_id = NULL, i.e. unowned legacy
        # tasks that no user will see until reassigned).
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in existing_columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")

        # Migration: databases created before the email notification feature
        # won't have an email column on users. Existing rows get NULL, i.e.
        # legacy users who won't receive notifications until they set one.
        existing_user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in existing_user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")

        conn.commit()
    finally:
        conn.close()


def _next_task_id(db):
    """Reserve and return the next task id, persisting the incremented counter."""
    db.execute("BEGIN IMMEDIATE")
    row = db.execute("SELECT value FROM counters WHERE name = 'task_id'").fetchone()
    next_id = row["value"]
    db.execute("UPDATE counters SET value = ? WHERE name = 'task_id'", (next_id + 1,))
    return next_id


def _task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


def _user_to_dict(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "created_at": row["created_at"],
    }


def _generate_token(user_id, secret_key):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(seconds=JWT_EXP_SECONDS),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def create_app(db_path=None, secret_key=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path or DEFAULT_DB_PATH
    app.config["SECRET_KEY"] = secret_key or os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    init_db(app.config["DB_PATH"])

    def get_db():
        db = getattr(g, "_database", None)
        if db is None:
            db = g._database = sqlite3.connect(app.config["DB_PATH"])
            db.row_factory = sqlite3.Row
        return db

    @app.teardown_appcontext
    def close_db(exception=None):
        db = g.pop("_database", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(e):
        return jsonify({"error": "Method not allowed"}), 405

    def require_auth(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing or invalid authorization header"}), 401

            token = auth_header[len("Bearer "):].strip()
            if not token:
                return jsonify({"error": "missing or invalid authorization header"}), 401

            try:
                payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[JWT_ALGORITHM])
            except jwt.PyJWTError:
                return jsonify({"error": "invalid or expired token"}), 401

            db = get_db()
            user = db.execute("SELECT * FROM users WHERE id = ?", (payload.get("sub"),)).fetchone()
            if user is None:
                return jsonify({"error": "invalid or expired token"}), 401

            g.current_user = user
            return view(*args, **kwargs)

        return wrapped

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")

        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            return jsonify(
                {"error": f"password is required and must be at least {MIN_PASSWORD_LENGTH} characters"}
            ), 400
        if email is not None and (not isinstance(email, str) or not email.strip()):
            return jsonify({"error": "email must be a non-empty string"}), 400

        username = username.strip()
        email = email.strip() if email is not None else f"{username}@example.com"
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing is not None:
            return jsonify({"error": "username already taken"}), 409

        password_hash = generate_password_hash(password)
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = db.execute(
            "INSERT INTO users (username, password_hash, email, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, email, created_at),
        )
        db.commit()

        row = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(_user_to_dict(row)), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return jsonify({"error": "username and password are required"}), 400

        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (username.strip(),)).fetchone()
        if row is None or not check_password_hash(row["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = _generate_token(row["id"], app.config["SECRET_KEY"])
        return jsonify({"token": token}), 200

    @app.post("/tasks")
    @require_auth
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        db = get_db()
        task_id = _next_task_id(db)
        created_at = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) VALUES (?, ?, ?, ?, ?)",
            (task_id, title, "pending", created_at, g.current_user["id"]),
        )
        db.commit()

        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify(_task_to_dict(row)), 201

    @app.get("/tasks")
    @require_auth
    def list_tasks():
        db = get_db()
        rows = db.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (g.current_user["id"],),
        ).fetchall()
        return jsonify([_task_to_dict(r) for r in rows]), 200

    @app.get("/tasks/<int:task_id>")
    @require_auth
    def get_task(task_id):
        db = get_db()
        row = db.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.current_user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404
        return jsonify(_task_to_dict(row)), 200

    @app.put("/tasks/<int:task_id>")
    @require_auth
    def update_task(task_id):
        db = get_db()
        row = db.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.current_user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": f"Task {task_id} not found"}), 404

        data = request.get_json(silent=True) or {}
        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400

        title = row["title"]
        previous_status = row["status"]
        status = previous_status

        if "title" in data:
            new_title = data["title"]
            if not isinstance(new_title, str) or not new_title.strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            title = new_title

        if "status" in data:
            new_status = data["status"]
            if not isinstance(new_status, str) or not new_status.strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            status = new_status

        db.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, task_id, g.current_user["id"]),
        )
        db.commit()

        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

        if previous_status != "completed" and status == "completed":
            owner_email = g.current_user["email"]
            if owner_email:
                try:
                    send_notification_email.delay(owner_email, row["title"])
                except Exception:
                    app.logger.exception("Failed to enqueue completion notification email")

        return jsonify(_task_to_dict(row)), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
