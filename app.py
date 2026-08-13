import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email


DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE)
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
        columns = {
            column["name"]
            for column in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "owner_id" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )


def task_to_dict(task: sqlite3.Row) -> dict:
    return {
        "id": task["id"],
        "title": task["title"],
        "status": task["status"],
        "created_at": task["created_at"],
    }


def json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def create_app(config: dict | None = None) -> Flask:
    global DATABASE

    application = Flask(__name__)
    application.config.from_mapping(
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-secret-change-me"),
        JWT_EXPIRATION_SECONDS=3600,
    )
    if config:
        application.config.update(config)
        if config.get("DATABASE"):
            DATABASE = config["DATABASE"]

    def token_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                return jsonify({"error": "authentication required"}), 401

            try:
                payload = jwt.decode(
                    token,
                    application.config["JWT_SECRET_KEY"],
                    algorithms=["HS256"],
                )
                user_id = int(payload["sub"])
            except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
                return jsonify({"error": "invalid token"}), 401

            with get_db() as connection:
                user = connection.execute(
                    "SELECT id, username FROM users WHERE id = ?", (user_id,)
                ).fetchone()
            if user is None:
                return jsonify({"error": "invalid token"}), 401

            g.user_id = user["id"]
            g.username = user["username"]
            return view(*args, **kwargs)

        return wrapped

    @application.post("/auth/register")
    def register():
        data = json_body()
        username = data.get("username") if data else None
        password = data.get("password") if data else None
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400

        try:
            with get_db() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username.strip(), generate_password_hash(password)),
                )
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409

        return jsonify({"id": cursor.lastrowid, "username": username.strip()}), 201

    @application.post("/auth/login")
    def login():
        data = json_body()
        username = data.get("username") if data else None
        password = data.get("password") if data else None
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify({"error": "username and password are required"}), 400

        with get_db() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ?", (username.strip(),)
            ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid credentials"}), 401

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user["id"]),
                "iat": now,
                "exp": now
                + timedelta(seconds=application.config["JWT_EXPIRATION_SECONDS"]),
            },
            application.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify({"token": token})

    @application.post("/tasks")
    @token_required
    def create_task():
        data = json_body()
        title = data.get("title") if data else None
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        title = title.strip()
        created_at = datetime.now(timezone.utc).isoformat()
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
                (title, created_at, g.user_id),
            )
            task = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()

        return jsonify(task_to_dict(task)), 201

    @application.get("/tasks")
    @token_required
    def list_tasks():
        with get_db() as connection:
            tasks = connection.execute(
                "SELECT * FROM tasks WHERE owner_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (g.user_id,),
            ).fetchall()
        return jsonify([task_to_dict(task) for task in tasks])

    @application.get("/tasks/<int:task_id>")
    @token_required
    def get_task(task_id: int):
        with get_db() as connection:
            task = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, g.user_id),
            ).fetchone()
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task_to_dict(task))

    @application.put("/tasks/<int:task_id>")
    @token_required
    def update_task(task_id: int):
        data = json_body()
        if data is None:
            return jsonify({"error": "JSON object is required"}), 400

        updates = []
        values = []
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            updates.append("title = ?")
            values.append(data["title"].strip())
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            updates.append("status = ?")
            values.append(data["status"].strip())
        if not updates:
            return jsonify({"error": "title or status is required"}), 400

        with get_db() as connection:
            existing = connection.execute(
                "SELECT id, status FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, g.user_id),
            ).fetchone()
            if existing is None:
                return jsonify({"error": "task not found"}), 404

            values.extend((task_id, g.user_id))
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} "
                "WHERE id = ? AND owner_id = ?",
                values,
            )
            task = connection.execute(
                "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
                (task_id, g.user_id),
            ).fetchone()

        if existing["status"] != "completed" and task["status"] == "completed":
            send_notification_email.delay(g.username, task["title"])

        return jsonify(task_to_dict(task))

    init_db()
    return application


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
