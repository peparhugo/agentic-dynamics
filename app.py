from flask import Flask, request, jsonify, g
from datetime import datetime, timezone, timedelta
import sqlite3
import os
import jwt
import bcrypt
from functools import wraps
from celery_config import send_notification_email

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
        cols = conn.execute("PRAGMA table_info(tasks)").fetchall()
        col_names = [c["name"] for c in cols]
        if "owner_id" not in col_names:
            conn.execute(
                "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
            )
        conn.commit()


def create_token(user_id):
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth[7:]

        if not token:
            return jsonify({"error": "token is missing"}), 401

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            g.user_id = data["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "token is invalid"}), 401

        return f(*args, **kwargs)

    return decorated


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return jsonify({"error": "username already exists"}), 409

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid

    token = create_token(user_id)
    return jsonify({"token": token, "user_id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    with get_db() as conn:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user:
            return jsonify({"error": "invalid username or password"}), 401

        if not bcrypt.checkpw(
            password.encode("utf-8"), user["password_hash"].encode("utf-8")
        ):
            return jsonify({"error": "invalid username or password"}), 401

        user_id = user["id"]

    token = create_token(user_id)
    return jsonify({"token": token, "user_id": user_id, "username": username}), 200


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, g.user_id),
        )
        conn.commit()
        task = {
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
        }
    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (g.user_id,),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    status = data.get("status")

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, g.user_id),
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404

        old_status = row["status"]
        old_title = row["title"]

        updates = []
        params = []

        if title is not None:
            title = title.strip()
            if not title:
                return jsonify({"error": "title is required"}), 400
            updates.append("title = ?")
            params.append(title)

        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if updates:
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()

        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if status is not None and status == "completed" and old_status != "completed":
            user = conn.execute(
                "SELECT username FROM users WHERE id = ?", (g.user_id,)
            ).fetchone()
            if user:
                user_email = f"{user['username']}@example.com"
                task_title_for_email = title if title is not None else old_title
                send_notification_email.delay(user_email, task_title_for_email)

    return jsonify(dict(row))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
