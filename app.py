"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timezone
import sqlite3
import os
import base64
import binascii
import hashlib
import hmac
import json
import time
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  username TEXT NOT NULL UNIQUE,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
             "  created_at TEXT NOT NULL,"
             "  owner_id INTEGER"
            ")"
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")


init_db()


# ── Models ────────────────────────────────────────────────────

def create_user(username: str, password: str) -> dict:
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "username": username}


def find_user(username: str) -> sqlite3.Row | None:
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def create_token(user_id: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "exp": int(time.time()) + 86400}

    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()

    unsigned = f"{encode(header)}.{encode(payload)}"
    signature = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def current_user_id() -> int | None:
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        encoded_header, encoded_payload, encoded_signature = authorization[7:].split(".")
        unsigned = f"{encoded_header}.{encoded_payload}"
        expected = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected, actual):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4)))
        if payload.get("exp", 0) < time.time() or not isinstance(payload.get("sub"), int):
            return None
        with get_db() as conn:
            if conn.execute("SELECT 1 FROM users WHERE id = ?", (payload["sub"],)).fetchone() is None:
                return None
        return payload["sub"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = current_user_id()
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def create_task(title: str, owner_id: int) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, owner_id),
        )
        conn.commit()
        return {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
        }


def get_tasks(owner_id: int):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)).fetchall()
        return [{key: row[key] for key in ("id", "title", "status", "created_at")} for row in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)).fetchone()
        return ({key: row[key] for key in ("id", "title", "status", "created_at")} if row else None)


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    task = get_task(task_id, owner_id)
    if task is None:
        return None
    with get_db() as conn:
        updates = []
        params = []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.extend((task_id, owner_id))
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND owner_id = ?", params
            )
            conn.commit()
    return get_task(task_id, owner_id)


# ── Routes ─────────────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    title = data.get("title", "")
    if not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    if get_task(task_id, g.user_id) is None:
        return jsonify({"error": "task not found"}), 404
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    if not data or not ("title" in data or "status" in data):
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and (not isinstance(data["status"], str) or not data["status"].strip()):
        return jsonify({"error": "status must be a non-empty string"}), 400
    task = update_task(
        task_id, g.user_id,
        title=data.get("title", None).strip() if "title" in data else None,
        status=data.get("status"),
    )
    return jsonify(task)


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        return jsonify({"error": "username and password are required"}), 400
    username, password = data["username"].strip(), data["password"]
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    if find_user(username) is not None:
        return jsonify({"error": "username already exists"}), 409
    try:
        user = create_user(username, password)
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        return jsonify({"error": "invalid credentials"}), 401
    user = find_user(data["username"])
    if user is None or not check_password_hash(user["password_hash"], data["password"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


if __name__ == "__main__":
    app.run(debug=True)
