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
import hashlib
import os
import secrets
import time

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
        """)


# ── Auth Utilities ──────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = app.config["SECRET_KEY"][:16]
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def create_token(user_id: int) -> str:
    token = secrets.token_hex(32)
    expires = (datetime.utcnow() + timedelta(seconds=TOKEN_TTL)).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user_id, expires),
        )
        conn.commit()
    return token


def get_user_from_token(token: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT u.* FROM users u JOIN tokens t ON u.id = t.user_id "
            "WHERE t.token = ? AND t.expires_at > ?",
            (token, datetime.utcnow().isoformat()),
        ).fetchone()
    return dict(row) if row else None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing authorization header"}), 401
        token = auth.split(" ", 1)[1]
        user = get_user_from_token(token)
        if user is None:
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
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, hash_password(password)),
        ).fetchone()
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"])
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
app.register_blueprint(admin_bp)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
