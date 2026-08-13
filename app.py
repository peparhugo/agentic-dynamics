"""Flask API for managing tasks stored in SQLite."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
import sqlite3
from functools import wraps

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["DATABASE"] = os.environ.get("DATABASE", "todos.db")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_HOURS"] = 24


def get_db() -> sqlite3.Connection:
    """Create a SQLite connection configured to return mapping-like rows."""
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create application tables and migrate existing task databases."""
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
            # Nullable ownership preserves task records created before auth existed.
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")


def encode_token(user_id: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int(
            (datetime.now(timezone.utc) + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"])).timestamp()
        ),
    }
    encoded_header = base64.urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode()
    ).rstrip(b"=")
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=")
    signing_input = encoded_header + b"." + encoded_payload
    signature = hmac.new(
        app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
    ).digest()
    return (signing_input + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def decode_token(token: str) -> int | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}".encode()
        expected_signature = hmac.new(
            app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
        ).digest()
        signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, int) or payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return user_id
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = decode_token(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return jsonify(error="authentication required"), 401
        return view(user_id, *args, **kwargs)

    return wrapped


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
    return dict(row) if row else None


def validate_title(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def validate_credentials(data: object) -> tuple[str, str] | None:
    if not isinstance(data, dict):
        return None
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return None
    return username.strip(), password


@app.post("/auth/register")
def register():
    credentials = validate_credentials(request.get_json(silent=True))
    if credentials is None:
        return jsonify(error="username and password are required"), 400

    username, password = credentials
    try:
        with get_db() as connection:
            connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
    except sqlite3.IntegrityError:
        return jsonify(error="username already exists"), 409
    return jsonify(username=username), 201


@app.post("/auth/login")
def login():
    credentials = validate_credentials(request.get_json(silent=True))
    if credentials is None:
        return jsonify(error="username and password are required"), 400

    username, password = credentials
    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=encode_token(user["id"]))


@app.post("/tasks")
@require_auth
def create_task(user_id: int):
    data = request.get_json(silent=True)
    title = validate_title(data.get("title")) if isinstance(data, dict) else None
    if title is None:
        return jsonify(error="title is required"), 400

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
            (title, created_at, user_id),
        )
        task_id = cursor.lastrowid

    return jsonify(get_task(task_id, user_id)), 201


@app.get("/tasks")
@require_auth
def list_tasks(user_id: int):
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(user_id: int, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(user_id: int, task_id: int):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON body is required"), 400

    updates = []
    parameters = []
    if "title" in data:
        title = validate_title(data["title"])
        if title is None:
            return jsonify(error="title must be a non-empty string"), 400
        updates.append("title = ?")
        parameters.append(title)
    if "status" in data:
        if not isinstance(data["status"], str):
            return jsonify(error="status must be a string"), 400
        updates.append("status = ?")
        parameters.append(data["status"])
    if not updates:
        return jsonify(error="title or status is required"), 400

    parameters.extend((task_id, user_id))
    with get_db() as connection:
        cursor = connection.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", parameters
        )
        if cursor.rowcount == 0:
            return jsonify(error="task not found"), 404

    return jsonify(get_task(task_id, user_id))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
