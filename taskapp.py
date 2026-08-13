"""Flask API for task management, backed by SQLite, with JWT authentication."""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))


def get_db(database: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(database: str) -> None:
    conn = get_db(database)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            owner_id INTEGER REFERENCES users(id)
        )
        """
    )
    # Migration: pre-existing databases created before owner_id was added
    # won't have the column yet, so add it without touching existing rows.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "owner_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
    conn.commit()
    conn.close()


def create_app(database: str = "tasks.db") -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-secret-key-change-me-in-production-please"
    )
    init_db(database)

    def db() -> sqlite3.Connection:
        return get_db(app.config["DATABASE"])

    def make_token(user_id: int, username: str) -> str:
        payload = {
            "sub": str(user_id),
            "username": username,
            "exp": datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS),
        }
        return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

    def require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing or invalid authorization header"}), 401
            token = auth_header[len("Bearer "):].strip()
            try:
                payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "invalid token"}), 401

            try:
                user_id = int(payload.get("sub"))
            except (TypeError, ValueError):
                return jsonify({"error": "invalid token"}), 401

            conn = db()
            try:
                user = conn.execute(
                    "SELECT * FROM users WHERE id = ?", (user_id,)
                ).fetchone()
            finally:
                conn.close()
            if user is None:
                return jsonify({"error": "invalid token"}), 401

            return f(user, *args, **kwargs)

        return wrapper

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "method not allowed"}), 405

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        username = username.strip()

        conn = db()
        try:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing is not None:
                return jsonify({"error": "username already taken"}), 409

            password_hash = generate_password_hash(password)
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            user_id = cur.lastrowid
        finally:
            conn.close()
        return jsonify({"id": user_id, "username": username}), 201

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        username = username.strip()

        conn = db()
        try:
            user = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        finally:
            conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = make_token(user["id"], user["username"])
        return jsonify({"token": token})

    @app.route("/tasks", methods=["POST"])
    @require_auth
    def create_task(user):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        now = datetime.now(timezone.utc).isoformat()
        conn = db()
        try:
            cur = conn.execute(
                "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
                (title.strip(), "pending", now, user["id"]),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        finally:
            conn.close()
        return jsonify(dict(row)), 201

    @app.route("/tasks", methods=["GET"])
    @require_auth
    def list_tasks(user):
        conn = db()
        try:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
                (user["id"],),
            ).fetchall()
        finally:
            conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    @require_auth
    def get_task(user, task_id):
        conn = db()
        try:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, user["id"])
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(dict(row))

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    @require_auth
    def update_task(user, task_id):
        conn = db()
        try:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, user["id"])
            ).fetchone()
            if row is None:
                return jsonify({"error": "task not found"}), 404

            data = request.get_json(silent=True) or {}
            if not data:
                return jsonify({"error": "no fields to update"}), 400

            title = row["title"]
            status = row["status"]

            if "title" in data:
                new_title = data.get("title")
                if not isinstance(new_title, str) or not new_title.strip():
                    return jsonify({"error": "title must be a non-empty string"}), 400
                title = new_title.strip()

            if "status" in data:
                new_status = data.get("status")
                if not isinstance(new_status, str) or not new_status.strip():
                    return jsonify({"error": "status must be a non-empty string"}), 400
                status = new_status.strip()

            conn.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        finally:
            conn.close()
        return jsonify(dict(row))

    return app


if __name__ == "__main__":
    application = create_app(os.environ.get("DATABASE", "tasks.db"))
    application.run(debug=True)
