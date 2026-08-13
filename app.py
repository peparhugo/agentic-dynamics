"""SQLite-backed task management API."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from tasks import send_notification_email


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-only-secret")
JWT_EXPIRATION_HOURS = 24


def get_db() -> sqlite3.Connection:
    """Return a connection that exposes rows by column name."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create and migrate the database schema without discarding existing tasks."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT,
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
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")


def encode_token(user_id: int) -> str:
    """Create a signed, expiring JWT for a user."""
    def encode_part(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    header = encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = encode_part(
        json.dumps(
            {
                "sub": user_id,
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{encode_part(signature)}"


def decode_token(token: str) -> int | None:
    """Validate a JWT and return its subject, or None when it is invalid."""
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if not isinstance(claims.get("sub"), int) or claims.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return claims["sub"]
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def authentication_required(view):
    """Require a valid bearer token and expose its user id to the view."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = decode_token(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        with get_db() as conn:
            user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def task_not_found():
    return jsonify({"error": "task not found"}), 404


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username.strip(), email.strip() if email else username.strip(), generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username.strip()}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username.strip(),)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": encode_token(user["id"])})


@app.post("/tasks")
@authentication_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    task = {
        "title": title.strip(),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
        "owner_id": g.user_id,
    }
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (task["title"], task["status"], task["created_at"], task["owner_id"]),
        )
        task["id"] = cursor.lastrowid
    del task["owner_id"]
    return jsonify(task), 201


@app.get("/tasks")
@authentication_required
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ?", (g.user_id,)
        ).fetchall()
    # SQLite retrieval is intentionally unsorted; sort the loaded task rows here.
    tasks = [dict(row) for row in rows]
    tasks.sort(key=lambda task: task["created_at"], reverse=True)
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
@authentication_required
def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    if row is None:
        return task_not_found()
    return jsonify(dict(row))


@app.put("/tasks/<int:task_id>")
@authentication_required
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    updates = []
    values = []

    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        updates.append("title = ?")
        values.append(title.strip())
    if "status" in data:
        status = data["status"]
        if not isinstance(status, str):
            return jsonify({"error": "status must be a string"}), 400
        updates.append("status = ?")
        values.append(status)

    with get_db() as conn:
        row = conn.execute(
            """
            SELECT tasks.id, tasks.status, tasks.title, users.email
            FROM tasks JOIN users ON users.id = tasks.owner_id
            WHERE tasks.id = ? AND tasks.owner_id = ?
            """,
            (task_id, g.user_id),
        ).fetchone()
        if row is None:
            return task_not_found()
        if updates:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
                values + [task_id, g.user_id],
            )
        task = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    if data.get("status") == "completed" and row["status"] != "completed":
        send_notification_email.delay(row["email"], task["title"])
    return jsonify(dict(task))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
