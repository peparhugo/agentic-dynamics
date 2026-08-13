import os
import sqlite3
import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "development-only-change-me"
)
app.config["JWT_EXPIRATION_SECONDS"] = 3600


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
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
    message = f"{header}.{payload}"
    signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
    ).digest()
    return f"{message}.{_base64url_encode(signature)}"


def decode_token(token):
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = json.loads(_base64url_decode(header_part))
        if header != {"alg": "HS256", "typ": "JWT"}:
            return None
        message = f"{header_part}.{payload_part}"
        expected_signature = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(
            _base64url_decode(signature_part), expected_signature
        ):
            return None
        payload = json.loads(_base64url_decode(payload_part))
        if payload.get("exp", 0) <= datetime.now(timezone.utc).timestamp():
            return None
        return int(payload["sub"])
    except (
        ValueError,
        TypeError,
        KeyError,
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401

        user_id = decode_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401
        with get_db() as connection:
            user = connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.current_user_id = user_id
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
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


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
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user["id"])})


def task_response(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.post("/tasks")
@login_required
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) "
            "VALUES (?, ?, ?, ?)",
            (title, "pending", created_at, g.current_user_id),
        )
        task_id = cursor.lastrowid

    return jsonify(
        {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }
    ), 201


@app.get("/tasks")
@login_required
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (g.current_user_id,),
        ).fetchall()
    return jsonify([task_response(row) for row in rows])


@app.get("/tasks/<int:task_id>")
@login_required
def get_task(task_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, g.current_user_id),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_response(row))


@app.put("/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body is required"}), 400

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

    with get_db() as connection:
        exists = connection.execute(
            "SELECT id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.current_user_id),
        ).fetchone()
        if exists is None:
            return jsonify({"error": "task not found"}), 404
        if updates:
            connection.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                (*values, task_id),
            )
        row = connection.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?",
            (task_id, g.current_user_id),
        ).fetchone()

    return jsonify(task_response(row))


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({"error": error.description}), error.code


init_db()


if __name__ == "__main__":
    app.run(debug=True)
