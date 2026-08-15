"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime
from functools import wraps
import base64
import binascii
import hashlib
import hmac
import json
import sqlite3
import os
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_LIFETIME_SECONDS = 3600
VALID_STATUSES = {"pending", "done"}


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
            "  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done')),"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        # Existing databases predate ownership.  ALTER TABLE preserves those rows;
        # legacy rows stay unowned and are therefore not exposed by the API.
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner_id ON tasks(owner_id)")


def create_user(username: str, password: str) -> dict:
    password_hash = generate_password_hash(password)
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return {"id": cursor.lastrowid, "username": username}


def find_user(username: str):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    now = int(datetime.utcnow().timestamp())
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({"sub": str(user_id), "iat": now, "exp": now + JWT_LIFETIME_SECONDS}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(app.config["JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def decode_token(token: str) -> int:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid token")
    signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    expected = hmac.new(app.config["JWT_SECRET"].encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64decode(parts[2])):
        raise ValueError("invalid token")
    header = json.loads(_b64decode(parts[0]))
    payload = json.loads(_b64decode(parts[1]))
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        raise ValueError("invalid token")
    if not isinstance(payload.get("sub"), str) or int(payload["exp"]) <= int(datetime.utcnow().timestamp()):
        raise ValueError("expired token")
    return int(payload["sub"])


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        try:
            user_id = decode_token(authorization[7:].strip())
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
            return jsonify({"error": "invalid or expired token"}), 401
        with get_db() as conn:
            user = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.user = user
        return view(*args, **kwargs)
    return wrapped


# ── Models ────────────────────────────────────────────────────

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
        rows = conn.execute("SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)).fetchone()
        return dict(row) if row else None


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


init_db()


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
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
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    user = find_user(username) if isinstance(username, str) and isinstance(password, str) else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"]), "user": {"id": user["id"], "username": user["username"]}})

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.user["id"]))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = create_task(title.strip(), g.user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    if get_task(task_id, g.user["id"]) is None:
        return jsonify({"error": "task not found"}), 404
    if "status" in data and data["status"] not in VALID_STATUSES:
        return jsonify({"error": "invalid status"}), 422
    if "title" in data and not isinstance(data["title"], str):
        return jsonify({"error": "title must be a string"}), 400
    task = update_task(
        task_id, g.user["id"],
        title=data.get("title"),
        status=data.get("status"),
    )
    return jsonify(task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
