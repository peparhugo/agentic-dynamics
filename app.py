import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_SECONDS"] = 3600
DATABASE = os.environ.get("DATABASE", "tasks.db")


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
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
        )


def _base64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    now = datetime.now(timezone.utc)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"])).timestamp()
        ),
    }
    segments = [
        _base64url_encode(json.dumps(part, separators=(",", ":")).encode())
        for part in (header, payload)
    ]
    signing_input = ".".join(segments).encode("ascii")
    signature = hmac.new(
        app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
    ).digest()
    return ".".join((*segments, _base64url_encode(signature)))


def decode_token(token):
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        expected_signature = hmac.new(
            app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
        ).digest()
        signature = _base64url_decode(signature_part)
        header = json.loads(_base64url_decode(header_part))
        payload = json.loads(_base64url_decode(payload_part))
        if header.get("alg") != "HS256" or not hmac.compare_digest(
            signature, expected_signature
        ):
            return None
        if not isinstance(payload.get("exp"), (int, float)) or payload["exp"] <= int(
            datetime.now(timezone.utc).timestamp()
        ):
            return None
        user_id = int(payload["sub"])
        return user_id if user_id > 0 else None
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            return jsonify({"error": "authentication required"}), 401

        user_id = decode_token(token)
        if user_id is None:
            return jsonify({"error": "invalid token"}), 401
        with get_db() as connection:
            user = connection.execute(
                "SELECT id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user is None:
            return jsonify({"error": "invalid token"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def credentials_from_request():
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


def task_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.post("/auth/register")
def register():
    credentials = credentials_from_request()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    try:
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": cursor.lastrowid, "username": username}), 201


@app.post("/auth/login")
def login():
    credentials = credentials_from_request()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


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
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (cursor.lastrowid, g.user_id),
        ).fetchone()

    return jsonify(task_to_dict(row)), 201


@app.get("/tasks")
@require_auth
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT * FROM tasks
            WHERE owner_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (g.user_id,),
        ).fetchall()
    return jsonify([task_to_dict(row) for row in rows])


@app.get("/tasks/<int:task_id>")
@require_auth
def get_task(task_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_to_dict(row))


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
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
            "SELECT id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
        if existing is None:
            return jsonify({"error": "task not found"}), 404
        connection.execute(
            f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?",
            (*values, task_id, g.user_id),
        )
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()

    return jsonify(task_to_dict(row))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
