"""Flask API for managing authenticated users' tasks in SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24


def get_db() -> sqlite3.Connection:
    """Return a connection configured to expose rows by column name."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Create the schema and safely add ownership to existing task databases."""
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
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
            row["name"] for row in connection.execute("PRAGMA table_info(tasks)")
        }
        if "owner_id" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)")
        }
        if "email" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN email TEXT")


def encode_token(user_id: int) -> str:
    """Create a signed, expiring JWT for a user."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    }
    header_part = base64.urlsafe_b64encode(json.dumps(header, separators=(",", ":")).encode()).rstrip(b"=")
    payload_part = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signing_input = header_part + b"." + payload_part
    signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def decode_token(token: str) -> int | None:
    """Return the authenticated user ID if the JWT is valid and current."""
    try:
        header_part, payload_part, signature_part = token.encode().split(b".")
        signing_input = header_part + b"." + payload_part
        expected_signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        signature = base64.urlsafe_b64decode(signature_part + b"=" * (-len(signature_part) % 4))
        payload = json.loads(base64.urlsafe_b64decode(payload_part + b"=" * (-len(payload_part) % 4)))
        if not hmac.compare_digest(signature, expected_signature) or payload["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return payload["sub"] if isinstance(payload["sub"], int) else None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def require_auth(view):
    """Require a valid bearer token and pass its user ID to the route."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = decode_token(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


def task_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def get_task(task_id: int, owner_id: int) -> sqlite3.Row | None:
    with get_db() as connection:
        return connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    email = data.get("email") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400

    try:
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username.strip(), email.strip() if isinstance(email, str) else None, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username.strip()}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "username and password are required"}), 400

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": encode_token(user["id"])})


@app.post("/tasks")
@require_auth
def create_task(owner_id: int):
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
            (title.strip(), created_at, owner_id),
        )
        task_id = cursor.lastrowid

    return jsonify(task_dict(get_task(task_id, owner_id))), 201


@app.get("/tasks")
@require_auth
def list_tasks(owner_id: int):
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC", (owner_id,)
        ).fetchall()
    return jsonify([task_dict(row) for row in rows])


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(owner_id: int, task_id: int):
    task = get_task(task_id, owner_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_dict(task))


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(owner_id: int, task_id: int):
    task = get_task(task_id, owner_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not any(key in data for key in ("title", "status")):
        return jsonify({"error": "title or status is required"}), 400

    title = task["title"]
    status = task["status"]
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title is required"}), 400
        title = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status is required"}), 400
        status = data["status"].strip()

    with get_db() as connection:
        connection.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, task_id, owner_id),
        )
        owner = connection.execute(
            "SELECT email FROM users WHERE id = ?", (owner_id,)
        ).fetchone()
    if task["status"] != "completed" and status == "completed" and owner["email"]:
        send_notification_email.delay(owner["email"], title)
    return jsonify(task_dict(get_task(task_id, owner_id)))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
