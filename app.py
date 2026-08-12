"""Flask API for managing user-owned tasks stored in SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os
import sqlite3

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "development-secret-key")
app.config["JWT_EXPIRATION_HOURS"] = 24


def get_db():
    """Open a database connection configured for the current application."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create or migrate the schema without discarding existing task rows."""
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
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def error(message, status_code):
    return jsonify({"error": message}), status_code


def issue_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm="HS256")


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return error("authentication required", 401)
        try:
            payload = jwt.decode(
                token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return error("invalid or expired token", 401)

        with get_db() as connection:
            user = connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user is None:
            return error("invalid or expired token", 401)
        g.user = user
        return view(*args, **kwargs)

    return wrapped


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip():
        return error("username is required", 400)
    if not isinstance(password, str) or not password:
        return error("password is required", 400)

    username = username.strip()
    try:
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return error("username already exists", 409)
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not isinstance(password, str):
        return error("username and password are required", 400)

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("invalid username or password", 401)
    return jsonify({"token": issue_token(user["id"]), "username": user["username"]})


@app.route("/tasks", methods=["POST"])
@authenticated
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return error("title is required", 400)

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
            (title, created_at, g.user["id"]),
        )
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return jsonify(task_json(row)), 201


@app.route("/tasks", methods=["GET"])
@authenticated
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (g.user["id"],),
        ).fetchall()
    return jsonify([task_json(row) for row in rows])


def find_task(task_id):
    with get_db() as connection:
        return connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, g.user["id"]),
        ).fetchone()


@app.route("/tasks/<int:task_id>", methods=["GET"])
@authenticated
def get_task(task_id):
    row = find_task(task_id)
    if row is None:
        return error("task not found", 404)
    return jsonify(task_json(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@authenticated
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("request body must be a JSON object", 400)

    fields = []
    values = []
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return error("title must be a non-empty string", 400)
        fields.append("title = ?")
        values.append(data["title"].strip())
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return error("status must be a non-empty string", 400)
        fields.append("status = ?")
        values.append(data["status"].strip())
    if not fields:
        return error("title or status is required", 400)

    values.append(task_id)
    with get_db() as connection:
        cursor = connection.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ? AND owner_id = ?",
            values + [g.user["id"]],
        )
        if cursor.rowcount == 0:
            return error("task not found", 404)
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return jsonify(task_json(row))


# Initialize the schema when the application module starts.
init_db()


if __name__ == "__main__":
    app.run(debug=True)
