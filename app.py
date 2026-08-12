"""Flask API for managing tasks."""

from datetime import datetime, timezone
from functools import wraps
import base64
import binascii
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "change-this-development-secret")


def get_db():
    """Open a database connection with rows accessible by column name."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the schema and migrate databases created by older versions."""
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
        task_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "owner_id" not in task_columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user):
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(
        json.dumps(
            {"sub": user["id"], "username": user["username"]},
            separators=(",", ":"),
        ).encode()
    )
    unsigned = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode(signature)}"


def decode_token(token):
    header, payload, signature = token.split(".")
    unsigned = f"{header}.{payload}".encode("ascii")
    expected = hmac.new(JWT_SECRET.encode(), unsigned, hashlib.sha256).digest()
    if not hmac.compare_digest(_decode(signature), expected):
        raise ValueError("invalid signature")
    decoded_header = json.loads(_decode(header))
    decoded_payload = json.loads(_decode(payload))
    if decoded_header.get("alg") != "HS256" or not isinstance(decoded_payload.get("sub"), int):
        raise ValueError("invalid token claims")
    return decoded_payload


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        try:
            claims = decode_token(authorization[7:])
            with get_db() as connection:
                user = connection.execute(
                    "SELECT * FROM users WHERE id = ?", (claims["sub"],)
                ).fetchone()
            if user is None:
                raise ValueError("unknown user")
        except (
            ValueError,
            KeyError,
            TypeError,
            binascii.Error,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):
            return jsonify({"error": "invalid token"}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
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
            user = connection.execute(
                "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    with get_db() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    if user is None or not isinstance(password, str) or not check_password_hash(
        user["password_hash"], password
    ):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user)})


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, created_at, owner_id) VALUES (?, ?, ?)",
            (title, created_at, g.user["id"]),
        )
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(task_json(row)), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC, id DESC",
            (g.user["id"],),
        ).fetchall()
    return jsonify([task_json(row) for row in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.user["id"])
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_json(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    updates = {}
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        updates["title"] = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status must be a non-empty string"}), 400
        updates["status"] = data["status"].strip()
    if not updates:
        return jsonify({"error": "title or status is required"}), 400

    with get_db() as connection:
        row = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.user["id"])
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        assignments = ", ".join(f"{field} = ?" for field in updates)
        connection.execute(
            f"UPDATE tasks SET {assignments} WHERE id = ? AND owner_id = ?",
            (*updates.values(), task_id, g.user["id"]),
        )
        updated = connection.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user["id"]),
        ).fetchone()
    return jsonify(task_json(updated))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
