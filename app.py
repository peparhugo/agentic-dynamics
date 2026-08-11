"""
Tier 2 Small seed — Multi-file Flask Auth API (Python, ~500 LOC)

A modular Flask app with Blueprints, JWT authentication, SQLite persistence,
and pytest tests. Designed as a baseline for tier 2 multi-session stories.
"""

from flask import Flask
from flask import Blueprint
from flask import request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import secrets
import jwt as pyjwt
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATABASE = os.environ.get("DATABASE", "auth_api.db")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "3600"))


# ── Database ────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                owner_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
        """)
    migrate_tasks_owner_id()


# ── Auth Utilities ──────────────────────────────────────────────


def migrate_tasks_owner_id():
    with get_db() as conn:
        columns = [col[1] for col in conn.execute("PRAGMA table_info(tasks)").fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
            conn.commit()


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def create_jwt(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(seconds=TOKEN_TTL),
        "iat": datetime.utcnow(),
    }
    return pyjwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing authorization header"}), 401
        token = auth.split(" ", 1)[1]
        try:
            payload = pyjwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            user = {"id": payload["sub"], "username": payload["username"], "role": payload["role"]}
        except (pyjwt.ExpiredSignatureError, pyjwt.InvalidTokenError):
            return jsonify({"error": "invalid or expired token"}), 401
        return f(user, *args, **kwargs)
    return decorated


# ── Auth Blueprint ──────────────────────────────────────────────

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return jsonify({"error": "username already taken"}), 409
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) "
            "VALUES (?, ?, 'user', ?)",
            (username, hash_password(password), now),
        )
        conn.commit()
    return jsonify({"message": "user registered", "username": username}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password required"}), 400
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if user is None or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_jwt(dict(user))
    return jsonify({"token": token, "username": user["username"], "role": user["role"]})


# ── Items Blueprint ─────────────────────────────────────────────

items_bp = Blueprint("items", __name__, url_prefix="/items")


@items_bp.route("", methods=["GET"])
@require_auth
def list_items(user: dict):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM items WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@items_bp.route("", methods=["POST"])
@require_auth
def create_item(user: dict):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO items (user_id, name, description, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user["id"], name, data.get("description", ""), now),
        )
        conn.commit()
        return jsonify({
            "id": cursor.lastrowid,
            "name": name,
            "description": data.get("description", ""),
            "created_at": now,
        }), 201


@items_bp.route("/<int:item_id>", methods=["GET"])
@require_auth
def get_item(user: dict, item_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM items WHERE id = ? AND user_id = ?",
            (item_id, user["id"]),
        ).fetchone()
    if row is None:
        return jsonify({"error": "item not found"}), 404
    return jsonify(dict(row))


@items_bp.route("/<int:item_id>", methods=["DELETE"])
@require_auth
def delete_item(user: dict, item_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM items WHERE id = ? AND user_id = ?",
            (item_id, user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": "item not found"}), 404
        conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
    return jsonify({"message": "item deleted"})


# ── Tasks Blueprint ─────────────────────────────────────────────

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("", methods=["POST"])
@require_auth
def create_task(user: dict):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, owner_id, created_at) VALUES (?, 'pending', ?, ?)",
            (title, user["id"], now),
        )
        conn.commit()
        return jsonify({
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
        }), 201


@tasks_bp.route("", methods=["GET"])
@require_auth
def list_tasks(user: dict):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, owner_id, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user: dict, task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, owner_id, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user["id"]),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(dict(row))


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user: dict, task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, owner_id, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        status = data.get("status")
        if title is not None:
            title = title.strip()
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400
            conn.execute("UPDATE tasks SET title = ? WHERE id = ?", (title, task_id))
        if status is not None:
            conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))
        conn.commit()
        row = conn.execute(
            "SELECT id, title, status, owner_id, created_at FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
    return jsonify(dict(row))


# ── Admin Blueprint ─────────────────────────────────────────────

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users", methods=["GET"])
@require_auth
def list_users(user: dict):
    if user.get("role") != "admin":
        return jsonify({"error": "admin access required"}), 403
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY created_at"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ── Register Blueprints ─────────────────────────────────────────

app.register_blueprint(auth_bp)
app.register_blueprint(items_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(admin_bp)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
