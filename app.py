import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config.update(
    JWT_SECRET=os.environ.get("JWT_SECRET", secrets.token_hex(32)),
    JWT_EXPIRATION_SECONDS=3600,
)
DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute("PRAGMA foreign_keys = ON")
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
            row["name"]
            for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
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
    header = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _base64url_encode(
        json.dumps(
            {
                "sub": str(user_id),
                "iat": int(now.timestamp()),
                "exp": int(
                    (now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"]))
                    .timestamp()
                ),
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(
        app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{_base64url_encode(signature)}"


def decode_token(token):
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        expected_signature = hmac.new(
            app.config["JWT_SECRET"].encode(), signing_input, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(
            _base64url_decode(signature_part), expected_signature
        ):
            return None
        header = json.loads(_base64url_decode(header_part))
        payload = json.loads(_base64url_decode(payload_part))
        if header.get("alg") != "HS256" or header.get("typ") != "JWT":
            return None
        if payload.get("exp", 0) <= datetime.now(timezone.utc).timestamp():
            return None
        user_id = int(payload["sub"])
    except (
        AttributeError,
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
    return dict(user) if user else None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token:
            return jsonify(error="authentication required"), 401
        user = decode_token(token)
        if user is None:
            return jsonify(error="invalid or expired token"), 401
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
            "SELECT id, title, status, created_at, owner_id FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (owner_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id, owner_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at, owner_id FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
    return dict(row) if row else None


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


def credentials_from_request():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, None
    return data.get("username"), data.get("password")


@app.post("/auth/register")
def register():
    username, password = credentials_from_request()
    if not isinstance(username, str) or not username.strip():
        return jsonify(error="username is required"), 400
    if not isinstance(password, str) or not password:
        return jsonify(error="password is required"), 400

    username = username.strip()
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
    username, password = credentials_from_request()
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify(error="invalid username or password"), 401
    with get_db() as connection:
        user = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (username.strip(),),
        ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(error="invalid username or password"), 401
    return jsonify(token=create_token(user["id"]))


@app.get("/tasks")
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.current_user["id"]))


@app.post("/tasks")
@require_auth
def add_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify(error="title is required"), 400
    return jsonify(create_task(title.strip(), g.current_user["id"])), 201


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
    if get_task(task_id, g.current_user["id"]) is None:
        return jsonify(error="task not found"), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="JSON object is required"), 400

    title = data.get("title")
    status = data.get("status")
    if "title" in data and (not isinstance(title, str) or not title.strip()):
        return jsonify(error="title must be a non-empty string"), 400
    if "status" in data and not isinstance(status, str):
        return jsonify(error="status must be a string"), 400

    task = update_task(
        task_id,
        g.current_user["id"],
        title=title.strip() if isinstance(title, str) else None,
        status=status,
    )
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
