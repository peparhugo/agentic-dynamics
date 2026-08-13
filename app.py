"""
Codebase seed — Minimal Flask Todo API (tier 1, good seams)

A single-file Flask app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session stories.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import sqlite3
import os
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-only-secret")
JWT_EXPIRATION_HOURS = 24


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
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "owner_id" not in columns:
            # Nullable ownership keeps pre-authentication task data readable in the DB.
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")


init_db()


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
            "owner_id": owner_id,
        }


def get_tasks(owner_id: int):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
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


def create_user(username: str, password: str) -> dict | None:
    with get_db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
        except sqlite3.IntegrityError:
            return None
        return {"id": cursor.lastrowid, "username": username}


def get_user_by_username(username: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def _encode_segment(value: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=").decode()


def _decode_segment(value: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


def create_token(user_id: int) -> str:
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = _encode_segment({
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    })
    signed = f"{header}.{payload}"
    signature = base64.urlsafe_b64encode(
        hmac.new(JWT_SECRET.encode(), signed.encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    return f"{signed}.{signature}"


def verify_token(token: str) -> int | None:
    try:
        header, payload, signature = token.split(".")
        expected = base64.urlsafe_b64encode(
            hmac.new(JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        claims = _decode_segment(payload)
        if not hmac.compare_digest(signature, expected) or claims["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return int(claims["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = verify_token(token) if scheme == "Bearer" and token else None
        if user_id is None:
            return jsonify({"error": "authentication required"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)
    return wrapped


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    user = create_user(username.strip(), password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid username or password"}), 401
    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user["id"])})

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    title = title.strip()
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
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400

    task = update_task(
        task_id,
        g.user_id,
        title=title.strip() if title is not None else None,
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    app.run(debug=True)
