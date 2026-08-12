"""
Task Management API

A Flask API backed by SQLite that provides CRUD operations for tasks.
Tasks are scoped to authenticated users via JWT authentication.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
import sqlite3
import os

import jwt
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
JWT_ALGORITHM = "HS256"
JWT_TTL_HOURS = 24


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def migrate(conn):
    """Additive migrations so existing data is preserved."""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()]
    if "owner_id" not in cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            );
        """)
        migrate(conn)
        conn.commit()


def _row_to_task(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
        "owner_id": row["owner_id"],
    }


def make_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(hours=JWT_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str):
    return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing token"}), 401
        token = auth[len("Bearer "):]
        try:
            payload = decode_token(token)
        except jwt.PyJWTError:
            return jsonify({"error": "invalid token"}), 401
        request.user_id = int(payload["sub"])
        request.username = payload["username"]
        return fn(*args, **kwargs)
    return wrapper


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password")
    if not username:
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409
        user_id = cursor.lastrowid
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify(
        {"token": make_token(row["id"], row["username"]), "username": row["username"]}
    ), 200


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    status = data.get("status", "pending")
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title.strip(), status, now, request.user_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    return jsonify(_row_to_task(row)), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (request.user_id,),
        ).fetchall()
    return jsonify([_row_to_task(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(_row_to_task(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id: int):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        title = data.get("title", row["title"])
        status = data.get("status", row["status"])
        if "title" in data and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title is required"}), 400
        if "status" in data and not isinstance(status, str):
            return jsonify({"error": "status must be a string"}), 400
        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
            (title.strip(), status, task_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(_row_to_task(updated))


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


init_db()

if __name__ == "__main__":
    app.run(debug=True)
