"""JWT-authenticated task management API backed by SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os
import sqlite3

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["TOKEN_TTL_SECONDS"] = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the schema and migrate databases created by older versions."""
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
                created_at TEXT NOT NULL,
                owner_id INTEGER REFERENCES users(id)
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "owner_id" not in columns:
            # Nullable keeps pre-existing tasks intact; new tasks always have an owner.
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def issue_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=app.config["TOKEN_TTL_SECONDS"]),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def authenticate_request(view):
    @wraps(view)
    def protected(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        token = header[7:].strip()
        if not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid token"}), 401

        with get_db() as connection:
            user = connection.execute(
                "SELECT id, username, password_hash FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        if user is None:
            return jsonify({"error": "invalid token"}), 401
        g.current_user = user
        return view(*args, **kwargs)

    return protected


def task_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


@app.post("/auth/register")
def register():
    data = json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400

    username = username.strip()
    with get_db() as connection:
        try:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": cursor.lastrowid, "username": username}), 201


@app.post("/auth/login")
def login():
    data = json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": issue_token(user["id"]), "username": user["username"]})


TASK_SELECT = "id, title, status, created_at, owner_id"


@app.post("/tasks")
@authenticate_request
def create_task():
    data = json_body()
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    status = data.get("status", "pending")
    if not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400

    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title.strip(), status, datetime.now(timezone.utc).isoformat(), g.current_user["id"]),
        )
        row = connection.execute(
            f"SELECT {TASK_SELECT} FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(task_dict(row)), 201


@app.get("/tasks")
@authenticate_request
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            f"SELECT {TASK_SELECT} FROM tasks WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (g.current_user["id"],),
        ).fetchall()
    return jsonify([task_dict(row) for row in rows])


def find_task(task_id):
    with get_db() as connection:
        return connection.execute(
            f"SELECT {TASK_SELECT} FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.current_user["id"]),
        ).fetchone()


@app.get("/tasks/<int:task_id>")
@authenticate_request
def get_task(task_id):
    row = find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_dict(row))


@app.put("/tasks/<int:task_id>")
@authenticate_request
def update_task(task_id):
    data = json_body()
    supplied_fields = {field for field in ("title", "status") if field in data}
    if not supplied_fields:
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        data["title"] = data["title"].strip()
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    with get_db() as connection:
        row = connection.execute(
            f"SELECT {TASK_SELECT} FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.current_user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        connection.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (data.get("title", row["title"]), data.get("status", row["status"]),
             task_id, g.current_user["id"]),
        )
        updated = connection.execute(
            f"SELECT {TASK_SELECT} FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(task_dict(updated))


init_db()


if __name__ == "__main__":
    app.run()
