"""Flask API for managing user-owned tasks stored in SQLite."""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, jsonify, g, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "tasks.db")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "development-secret")
app.config["JWT_EXPIRATION_HOURS"] = 24


def get_db():
    """Create a database connection configured to return mapping-like rows."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create storage and migrate databases created before task ownership."""
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
                owner_id INTEGER
            )
            """
        )
        columns = {column["name"] for column in connection.execute("PRAGMA table_info(tasks)")}
        # Existing task rows remain intact; new tasks always receive an owner.
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        connection.execute("CREATE INDEX IF NOT EXISTS tasks_owner_id_idx ON tasks(owner_id)")


def task_response(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def get_task(task_id, owner_id):
    with get_db() as connection:
        return connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()


def token_required(view):
    """Require a signed, unexpired Bearer token and expose its user id."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(
                token, app.config["JWT_SECRET_KEY"], algorithms=["HS256"]
            )
            g.user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
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


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": str(user["id"]),
            "iat": now,
            "exp": now + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"]),
        },
        app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    return jsonify({"token": token})


@app.post("/tasks")
@token_required
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
            (title.strip(), created_at, g.user_id),
        )
        task = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (cursor.lastrowid, g.user_id),
        ).fetchone()
    return jsonify(task_response(task)), 201


@app.get("/tasks")
@token_required
def list_tasks():
    with get_db() as connection:
        tasks = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (g.user_id,),
        ).fetchall()
    return jsonify([task_response(task) for task in tasks])


@app.get("/tasks/<int:task_id>")
@token_required
def retrieve_task(task_id):
    task = get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_response(task))


@app.put("/tasks/<int:task_id>")
@token_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body is required"}), 400

    fields = []
    values = []
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        fields.append("title = ?")
        values.append(data["title"].strip())
    if "status" in data:
        if not isinstance(data["status"], str):
            return jsonify({"error": "status must be a string"}), 400
        fields.append("status = ?")
        values.append(data["status"])
    if not fields:
        return jsonify({"error": "title or status is required"}), 400

    with get_db() as connection:
        result = connection.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ? AND owner_id = ?",
            values + [task_id, g.user_id],
        )
        if result.rowcount == 0:
            return jsonify({"error": "task not found"}), 404
        task = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    return jsonify(task_response(task))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
