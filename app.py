"""
Tier 2 Small seed — Multi-file Flask Auth API (Python, ~500 LOC)

A modular Flask app with Blueprints, JWT authentication, SQLite persistence,
and pytest tests. Designed as a baseline for tier 2 multi-session stories.
"""

from flask import Flask
from flask import Blueprint
from flask import request, jsonify
from datetime import datetime, timedelta, timezone
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import hashlib
import os
import secrets
import time
import jwt

from notifications import send_notification_email

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATABASE = os.environ.get("DATABASE", "auth_api.db")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL", "3600"))
JWT_ALGORITHM = "HS256"


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
                email TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
        """)
    _migrate_legacy_schema()
    _migrate_add_columns()


def _migrate_legacy_schema():
    """Migrate pre-JWT installs: rename items -> tasks, user_id -> owner_id,
    drop the now-unused stateless-auth tokens table. Safe to run repeatedly
    and never drops user or task rows."""
    with get_db() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        if "items" in tables:
            item_cols = {row["name"] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
            owner_col = "owner_id" if "owner_id" in item_cols else "user_id"
            conn.execute(
                f"INSERT INTO tasks (id, owner_id, name, description, created_at) "
                f"SELECT id, {owner_col}, name, description, created_at FROM items "
                f"WHERE id NOT IN (SELECT id FROM tasks)"
            )
            conn.execute("DROP TABLE items")

        if "tokens" in tables:
            conn.execute("DROP TABLE tokens")

        conn.commit()


def _migrate_add_columns():
    """Add columns introduced after the initial schema (email, status) to
    pre-existing databases. Safe to run repeatedly."""
    with get_db() as conn:
        user_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "email" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
            conn.execute("UPDATE users SET email = username || '@example.com' WHERE email = ''")

        task_cols = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
        if "status" not in task_cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")

        conn.commit()


# ── Auth Utilities ──────────────────────────────────────────────

def hash_password(password: str) -> str:
    return generate_password_hash(password)


def _is_legacy_hash(password_hash: str) -> bool:
    # Legacy scheme: sha256("static_salt_1234:" + password) -> 64 hex chars
    return len(password_hash) == 64 and all(c in "0123456789abcdef" for c in password_hash)


def verify_password(password: str, password_hash: str) -> bool:
    if _is_legacy_hash(password_hash):
        salt = "static_salt_1234"
        return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == password_hash
    return check_password_hash(password_hash, password)


def create_token(user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(seconds=TOKEN_TTL),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=JWT_ALGORITHM)


def get_user_from_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
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
    email = data.get("email", "").strip() or f"{username}@example.com"
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
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO users (username, password_hash, role, email, created_at) "
            "VALUES (?, ?, 'user', ?, ?)",
            (username, hash_password(password), email, now),
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
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        user = None
        if row is not None and verify_password(password, row["password_hash"]):
            user = dict(row)
            if _is_legacy_hash(row["password_hash"]):
                # Lazily upgrade legacy sha256 hashes to werkzeug's scheme on successful login.
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password(password), user["id"]),
                )
                conn.commit()
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"], user["username"])
    return jsonify({"token": token, "username": user["username"], "role": user["role"]})


# ── Tasks Blueprint ─────────────────────────────────────────────

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("", methods=["GET"])
@require_auth
def list_tasks(user: dict):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@tasks_bp.route("", methods=["POST"])
@require_auth
def create_task(user: dict):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    with get_db() as conn:
        now = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (owner_id, name, description, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user["id"], name, data.get("description", ""), now),
        )
        conn.commit()
        return jsonify({
            "id": cursor.lastrowid,
            "name": name,
            "description": data.get("description", ""),
            "status": "pending",
            "created_at": now,
        }), 201


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user: dict, task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user["id"]),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(dict(row))


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user: dict, task_id: int):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404

        name = data.get("name", row["name"])
        description = data.get("description", row["description"])
        status = data.get("status", row["status"])

        conn.execute(
            "UPDATE tasks SET name = ?, description = ?, status = ? WHERE id = ?",
            (name, description, status, task_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if status == "completed" and row["status"] != "completed":
        send_notification_email.delay(user["email"], updated["name"])

    return jsonify(dict(updated))


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task(user: dict, task_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, user["id"]),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    return jsonify({"message": "task deleted"})


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
app.register_blueprint(tasks_bp)
app.register_blueprint(admin_bp)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
