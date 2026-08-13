"""SQLite-backed task management API."""

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email


def create_app(database: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["DATABASE"] = database or os.environ.get("DATABASE", "tasks.db")
    app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-only-secret")

    def get_db() -> sqlite3.Connection:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        return connection

    def init_db() -> None:
        with get_db() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
            if "owner_id" not in columns:
                # Nullable preserves rows created before task ownership was introduced.
                connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")

    def encode_token(user_id: int) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": user_id, "exp": int(time.time()) + 3600}

        def encode_part(value: dict) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode()
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

        signing_input = f"{encode_part(header)}.{encode_part(payload)}"
        signature = hmac.new(
            current_app.config["JWT_SECRET"].encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        return f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

    def decode_token(token: str) -> int | None:
        try:
            header, payload, signature = token.split(".")
            signing_input = f"{header}.{payload}"
            expected = hmac.new(
                current_app.config["JWT_SECRET"].encode(), signing_input.encode(), hashlib.sha256
            ).digest()
            supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
            if not hmac.compare_digest(supplied, expected):
                return None
            data = json.loads(
                base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
            )
            user_id = data.get("sub")
            if not isinstance(user_id, int) or data.get("exp", 0) < time.time():
                return None
            return user_id
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    def require_auth(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            user_id = decode_token(token) if scheme == "Bearer" and token else None
            if user_id is None:
                return jsonify({"error": "unauthorized"}), 401
            with get_db() as connection:
                user = connection.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if user is None:
                return jsonify({"error": "unauthorized"}), 401
            g.user_id = user_id
            return view(*args, **kwargs)

        return wrapped

    def task_or_404(task_id: int) -> sqlite3.Row | None:
        with get_db() as connection:
            task = connection.execute(
                """
                SELECT tasks.id, tasks.title, tasks.status, tasks.created_at, users.username AS owner_email
                FROM tasks JOIN users ON users.id = tasks.owner_id
                WHERE tasks.id = ? AND tasks.owner_id = ?
                """,
                (task_id, g.user_id),
            ).fetchone()
        return task

    def task_response(task: sqlite3.Row, updates: dict | None = None) -> dict:
        response = dict(task)
        response.pop("owner_email", None)
        if updates:
            response.update(updates)
        return response

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True)
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return jsonify({"error": "username and password are required"}), 400
        try:
            with get_db() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username.strip(), generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409
        return jsonify({"id": cursor.lastrowid, "username": username.strip()}), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True)
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify({"error": "invalid credentials"}), 401
        with get_db() as connection:
            user = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username.strip(),)
            ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid credentials"}), 401
        return jsonify({"token": encode_token(user["id"])})

    @app.post("/tasks")
    @require_auth
    def create_task():
        data = request.get_json(silent=True)
        title = data.get("title") if isinstance(data, dict) else None
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        title = title.strip()
        created_at = datetime.now(timezone.utc).isoformat()
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
                (title, created_at, g.user_id),
            )
        return jsonify({
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }), 201

    @app.get("/tasks")
    @require_auth
    def list_tasks():
        with get_db() as connection:
            tasks = connection.execute(
                "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
                (g.user_id,),
            ).fetchall()
        return jsonify([dict(task) for task in tasks])

    @app.get("/tasks/<int:task_id>")
    @require_auth
    def get_task(task_id: int):
        task = task_or_404(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task_response(task))

    @app.put("/tasks/<int:task_id>")
    @require_auth
    def update_task(task_id: int):
        task = task_or_404(task_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not {"title", "status"} & data.keys():
            return jsonify({"error": "title or status is required"}), 400

        updates = {}
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            updates["title"] = data["title"].strip()
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            updates["status"] = data["status"].strip()

        assignments = ", ".join(f"{column} = ?" for column in updates)
        with get_db() as connection:
            connection.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
                (*updates.values(), task_id, g.user_id),
            )
        if task["status"] != "completed" and updates.get("status") == "completed":
            send_notification_email.delay(task["owner_email"], updates.get("title", task["title"]))
        return jsonify(task_response(task, updates))

    with app.app_context():
        init_db()

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
