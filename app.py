"""
Task Management Flask API

Provides CRUD endpoints for tasks backed by SQLite, protected by JWT
authentication.

Users register/login and receive a JWT that must be sent in the
Authorization header for all /tasks/* endpoints. Each user only sees
and modifies their own tasks.

The tasks table intentionally does NOT use AUTOINCREMENT on its primary
key, so the id is assigned manually on every POST by computing
max(existing id) + 1 and inserting it explicitly.
"""

from datetime import datetime
import hashlib
import hmac
import os
import secrets
import sqlite3

from flask import Flask, jsonify, request

import jwt

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")

# In production this must come from an environment variable / secret store.
# Falls back to a random value so tokens are unpredictable across restarts.
JWT_SECRET = os.environ.get(
    "JWT_SECRET", secrets.token_hex(32).encode()
)
JWT_ALGORITHM = "HS256"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), JWT_SECRET, 100_000
    ).hex()


def _check_password(password, password_hash):
    return hmac.compare_digest(_hash_password(password), password_hash)


def _encode_token(user_id):
    return jwt.encode(
        {"user_id": user_id}, JWT_SECRET, algorithm=JWT_ALGORITHM
    )


def _decode_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return None


def _current_user_id():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    payload = _decode_token(header[7:].strip())
    if payload is None:
        return None
    return payload.get("user_id")


def init_db():
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER
            )
            """
        )
        # Migration: add owner_id to pre-existing tasks without breaking data.
        columns = [
            row["name"]
            for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        ]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def _next_id(conn):
    row = conn.execute("SELECT MAX(id) AS max_id FROM tasks").fetchone()
    max_id = row["max_id"] if row and row["max_id"] is not None else 0
    return max_id + 1


def _serialize(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _require_auth():
    user_id = _current_user_id()
    if user_id is None:
        return None
    with get_db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if user is None:
        return None
    return user_id


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not str(username).strip():
        return jsonify({"error": "username is required"}), 400
    if not password or not str(password):
        return jsonify({"error": "password is required"}), 400
    username = str(username).strip()
    password = str(password)
    password_hash = _hash_password(password)
    try:
        with get_db() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return (
        jsonify(
            {"id": user_id, "username": username, "token": _encode_token(user_id)}
        ),
        201,
    )


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (str(username).strip(),)
        ).fetchone()
    if user is None or not _check_password(str(password), user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify(
        {"id": user["id"], "username": user["username"], "token": _encode_token(user["id"])}
    )


@app.route("/tasks", methods=["POST"])
def create_task():
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "authentication required"}), 401
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not title or not str(title).strip():
        return jsonify({"error": "title is required"}), 400
    title = str(title).strip()
    status = data.get("status") or "pending"
    created_at = datetime.utcnow().isoformat()
    with get_db() as conn:
        task_id = _next_id(conn)
        conn.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) VALUES (?, ?, ?, ?, ?)",
            (task_id, title, status, created_at, user_id),
        )
        conn.commit()
    return (
        jsonify(
            {
                "id": task_id,
                "title": title,
                "status": status,
                "created_at": created_at,
            }
        ),
        201,
    )


@app.route("/tasks", methods=["GET"])
def list_tasks():
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "authentication required"}), 401
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return jsonify([_serialize(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "authentication required"}), 401
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(_serialize(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    user_id = _require_auth()
    if user_id is None:
        return jsonify({"error": "authentication required"}), 401
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        title = data.get("title", row["title"])
        status = data.get("status", row["status"])
        if not title or not str(title).strip():
            return jsonify({"error": "title is required"}), 400
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (str(title).strip(), str(status).strip(), task_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user_id),
        ).fetchone()
    return jsonify(_serialize(updated))


init_db()


if __name__ == "__main__":
    app.run(debug=True)
