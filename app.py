"""A small SQLite-backed task management API with JWT authentication."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from functools import wraps
import hashlib
import hmac
import json
import os
import sqlite3

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from notifications import send_notification_email


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
TOKEN_LIFETIME = timedelta(hours=24)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the schema and migrate databases created by older versions."""
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
            "  id INTEGER PRIMARY KEY,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER REFERENCES users(id)"
            ")"
        )
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "owner_id" not in columns:
            # Nullable preserves existing tasks while allowing new authenticated data.
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        conn.commit()


def _encode_part(value: bytes) -> str:
    return urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_part(value: str) -> bytes:
    return urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(json.dumps({
        "sub": str(user_id),
        "exp": int((datetime.now(timezone.utc) + TOKEN_LIFETIME).timestamp()),
    }, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}"
    signature = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{_encode_part(signature)}"


def decode_token(token: str) -> int | None:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(JWT_SECRET.encode(), unsigned.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_decode_part(signature), expected):
            return None
        header_data = json.loads(_decode_part(header))
        data = json.loads(_decode_part(payload))
        if header_data.get("alg") != "HS256" or int(data["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            return None
        user_id = int(data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError, Exception):
        return None
    return user_id


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        user_id = decode_token(authorization[7:].strip())
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401
        with get_db() as conn:
            user = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.current_user = dict(user)
        return view(*args, **kwargs)

    return wrapped


def create_task(title: str, owner_id: int | None = None) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        next_id = conn.execute("SELECT COALESCE(MAX(id) + 1, 0) FROM tasks").fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO tasks (id, title, status, created_at, owner_id) VALUES (?, ?, 'pending', ?, ?)",
            (next_id, title, now, owner_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone())


def get_tasks(owner_id: int | None = None):
    with get_db() as conn:
        if owner_id is None:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int | None = None) -> dict | None:
    with get_db() as conn:
        if owner_id is None:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, owner_id)).fetchone()
        return dict(row) if row else None


def fetch_task(task_id: int) -> dict | None:
    """Compatibility alias for callers using the original helper name."""
    return get_task(task_id)


def update_task(task_id: int, title: str | None = None, status: str | None = None, owner_id: int | None = None) -> dict | None:
    task = get_task(task_id, owner_id)
    if task is None:
        return None
    with get_db() as conn:
        updates, params = [], []
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if updates:
            params.extend([task_id] if owner_id is None else [task_id, owner_id])
            where = "id = ?" if owner_id is None else "id = ? AND owner_id = ?"
            conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE {where}", params)
            conn.commit()
    return get_task(task_id, owner_id)


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "username and password are required"}), 400
    username, password = data.get("username"), data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    try:
        with get_db() as conn:
            cursor = conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, generate_password_hash(password)))
            conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": cursor.lastrowid, "username": username}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "invalid credentials"}), 401
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (data.get("username"),)).fetchone()
    if user is None or not isinstance(data.get("password"), str) or not check_password_hash(user["password_hash"], data["password"]):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": create_token(user["id"])})


@app.route("/tasks", methods=["GET"])
@authenticated
def list_tasks():
    return jsonify(get_tasks(g.current_user["id"]))


@app.route("/tasks", methods=["POST"])
@authenticated
def add_task():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title.strip(), g.current_user["id"])), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@authenticated
def show_task(task_id: int):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@authenticated
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400
    previous_task = get_task(task_id, g.current_user["id"])
    task = update_task(task_id, data.get("title"), data.get("status"), g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        send_notification_email.delay(g.current_user["username"], task["title"])
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
