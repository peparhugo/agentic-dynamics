from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import sqlite3
import os
from tasks import send_notification_email

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def get_db():
    conn = sqlite3.connect(os.environ.get("DATABASE", "tasks.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT
            )
        """)
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            return jsonify({"error": "token is missing"}), 401
        try:
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            request.user_id = payload["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "token is expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "token is invalid"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    email = data.get("email", "").strip() or f"{username}@example.com"
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            return jsonify({"error": "username already exists"}), 409
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
            (username, password_hash, email),
        )
        conn.commit()
        return jsonify({
            "id": cursor.lastrowid,
            "username": username,
        }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401
        token = jwt.encode(
            {
                "user_id": user["id"],
                "exp": datetime.utcnow() + timedelta(hours=24),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify({"token": token})


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
            (title, now, request.user_id),
        )
        conn.commit()
        return jsonify({
            "id": cursor.lastrowid,
            "title": title,
            "status": "pending",
            "created_at": now,
            "owner_id": request.user_id,
        }), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (request.user_id,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id)
        ).fetchone()
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id)
        ).fetchone()
        if row is None:
            return jsonify({"error": "task not found"}), 404

        data = request.get_json(silent=True) or {}
        title = data.get("title", row["title"]).strip() if data.get("title") is not None else row["title"]
        status = data.get("status", row["status"])
        old_status = row["status"]

        conn.execute(
            "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
            (title, status, task_id, request.user_id),
        )
        conn.commit()

        if old_status != "completed" and status == "completed":
            user = conn.execute(
                "SELECT * FROM users WHERE id = ?", (request.user_id,)
            ).fetchone()
            user_email = user["email"] if user and user["email"] else f"user{request.user_id}@example.com"
            send_notification_email.delay(user_email, title)

        updated = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, request.user_id)
        ).fetchone()
    return jsonify(dict(updated))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
