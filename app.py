import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_LIFETIME = timedelta(hours=1)


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
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
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER REFERENCES users(id)
            )
            """
        )
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        if "owner_id" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def error(message, status_code):
    return jsonify({"error": message}), status_code


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return error("authentication required", 401)

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return error("invalid token", 401)

        with get_db() as connection:
            user = connection.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user is None:
            return error("invalid token", 401)
        return view(user_id, *args, **kwargs)

    return wrapped


def credentials():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return None
    if not isinstance(password, str) or not password:
        return None
    return username.strip(), password


@app.post("/auth/register")
def register():
    values = credentials()
    if values is None:
        return error("username and password are required", 400)
    username, password = values

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


@app.post("/auth/login")
def login():
    values = credentials()
    if values is None:
        return error("username and password are required", 400)
    username, password = values

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("invalid credentials", 401)

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user["id"]), "iat": now, "exp": now + JWT_LIFETIME},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return jsonify({"token": token})


@app.post("/tasks")
@require_auth
def create_task(user_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("title is required", 400)

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return error("title is required", 400)

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    connection = get_db()
    try:
        # Reserve the database for writing while deriving the next ID.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM tasks"
        ).fetchone()
        task_id = row["next_id"]
        connection.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_id, title, "pending", created_at, user_id),
        )
        connection.commit()
    finally:
        connection.close()

    return jsonify(
        {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }
    ), 201


@app.get("/tasks")
@require_auth
def list_tasks(user_id):
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return jsonify([task_json(row) for row in rows])


@app.get("/tasks/<int:task_id>")
@require_auth
def get_task(user_id, task_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()
    if row is None:
        return error("task not found", 404)
    return jsonify(task_json(row))


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(user_id, task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("JSON object is required", 400)

    updates = []
    values = []

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            return error("title must be a non-empty string", 400)
        updates.append("title = ?")
        values.append(title.strip())

    if "status" in data:
        status = data["status"]
        if not isinstance(status, str) or not status.strip():
            return error("status must be a non-empty string", 400)
        updates.append("status = ?")
        values.append(status.strip())

    if not updates:
        return error("title or status is required", 400)

    with get_db() as connection:
        existing = connection.execute(
            "SELECT id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()
        if existing is None:
            return error("task not found", 404)

        values.extend((task_id, user_id))
        connection.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
            values,
        )
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()

    return jsonify(task_json(row))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
