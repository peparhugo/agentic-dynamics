import base64
import binascii
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "development-secret-change-in-production"
)
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
            # Nullable ownership preserves legacy rows without exposing them to users.
            connection.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)"
        )


def _base64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(user_id):
    header = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    now = int(time.time())
    payload = _base64url_encode(
        json.dumps(
            {
                "sub": str(user_id),
                "iat": now,
                "exp": now + app.config["JWT_EXPIRATION_SECONDS"],
            },
            separators=(",", ":"),
        ).encode()
    )
    message = f"{header}.{payload}"
    signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
    ).digest()
    return f"{message}.{_base64url_encode(signature)}"


def decode_token(token):
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        message = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
        ).digest()
        signature = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(signature, expected_signature):
            return None

        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        if not isinstance(header, dict) or not isinstance(payload, dict):
            return None
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return None
        if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(time.time()):
            return None
        user_id = int(payload["sub"])
    except (
        binascii.Error,
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return dict(user) if user is not None else None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not separator or not token:
            return jsonify(error="authentication required"), 401

        user = decode_token(token)
        if user is None:
            return jsonify(error="invalid token"), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def create_task(title, owner_id):
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
            (title, created_at, owner_id),
        )
        task_id = cursor.lastrowid
    return get_task(task_id, owner_id)


def get_tasks(owner_id):
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id, owner_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
    return dict(row) if row is not None else None


def update_task(task_id, owner_id, title=None, status=None):
    if get_task(task_id, owner_id) is None:
        return None

    updates = []
    values = []
    if title is not None:
        updates.append("title = ?")
        values.append(title)
    if status is not None:
        updates.append("status = ?")
        values.append(status)

    if updates:
        values.extend((task_id, owner_id))
        with get_db() as connection:
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} "
                "WHERE id = ? AND owner_id = ?",
                values,
            )
    return get_task(task_id, owner_id)


def json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def credentials():
    data = json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return None, None
    if not isinstance(password, str) or not password:
        return None, None
    return username.strip(), password


@app.post("/auth/register")
def register():
    username, password = credentials()
    if username is None:
        return jsonify(error="username and password are required"), 400

    try:
        with get_db() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify(error="username already exists"), 409
    return jsonify(id=user_id, username=username), 201


@app.post("/auth/login")
def login():
    username, password = credentials()
    if username is None:
        return jsonify(error="username and password are required"), 400

    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid credentials"), 401
    return jsonify(token=create_token(user["id"]))


@app.post("/tasks")
@require_auth
def add_task():
    title = json_body().get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400
    return jsonify(create_task(title.strip(), g.current_user["id"])), 201


@app.get("/tasks")
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.current_user["id"]))


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(task_id):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def edit_task(task_id):
    data = json_body()
    if "title" in data and (
        not isinstance(data["title"], str) or not data["title"].strip()
    ):
        return jsonify(error="title must be a non-empty string"), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify(error="status must be a string"), 400

    task = update_task(
        task_id,
        g.current_user["id"],
        title=data["title"].strip() if "title" in data else None,
        status=data.get("status"),
    )
    if task is None:
        return jsonify(error="task not found"), 404
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run()
