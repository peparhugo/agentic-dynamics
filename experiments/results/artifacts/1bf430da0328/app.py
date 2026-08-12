import functools
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = os.environ.get("DATABASE", "tasks.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)")
        except sqlite3.OperationalError:
            pass
        conn.commit()


def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token):
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload["user_id"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError):
        return None


def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid token"}), 401
        token = auth_header[7:]
        user_id = decode_token(token)
        if user_id is None:
            return jsonify({"error": "missing or invalid token"}), 401
        request.user_id = user_id
        return f(*args, **kwargs)

    return decorated


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    password_hash = generate_password_hash(password)

    with get_db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409

    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401

    token = create_token(row["id"])
    return jsonify({"token": token})


# ---------------------------------------------------------------------------
# Task endpoints (protected)
# ---------------------------------------------------------------------------


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, request.user_id),
        )
        conn.commit()
        task_id = cur.lastrowid

    return (
        jsonify(
            {
                "id": task_id,
                "title": title,
                "status": "pending",
                "created_at": now,
                "owner_id": request.user_id,
            }
        ),
        201,
    )


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (request.user_id,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True) or {}
        title = data.get("title")
        status = data.get("status")

        updates = {}
        if title is not None and isinstance(title, str) and title.strip():
            updates["title"] = title.strip()
        if status is not None and isinstance(status, str) and status.strip():
            updates["status"] = status.strip()

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [task_id, request.user_id]
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ? AND owner_id = ?",
                values,
            )
            conn.commit()

        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id),
        ).fetchone()

    return jsonify(dict(row))


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(debug=True)
