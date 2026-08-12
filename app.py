"""Flask API for managing tasks stored in SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import sqlite3
import os

from flask import Flask, jsonify, request
import jwt
from werkzeug.security import check_password_hash, generate_password_hash
from tasks import send_notification_email

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_LIFETIME = timedelta(hours=1)


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
            "  password_hash TEXT NOT NULL,"
            "  email TEXT"
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
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "email" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        # Existing tasks remain available to the compatibility user rather than
        # becoming inaccessible after the ownership migration.
        legacy = conn.execute(
            "SELECT id FROM users WHERE username = ?", ("legacy",)
        ).fetchone()
        if legacy is None:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("legacy", generate_password_hash(os.urandom(16).hex())),
            )
            legacy_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            legacy_id = legacy[0]
        conn.execute("UPDATE tasks SET owner_id = ? WHERE owner_id IS NULL", (legacy_id,))
        conn.commit()


# ── Models ────────────────────────────────────────────────────

def create_task(title: str, owner_id: int) -> dict:
    with get_db() as conn:
        now = datetime.now(timezone.utc).isoformat()
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
        rows = conn.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE owner_id = ? ORDER BY created_at DESC", (owner_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at FROM tasks "
            "WHERE id = ? AND owner_id = ?", (task_id, owner_id)
        ).fetchone()
        return dict(row) if row else None


def get_user_email(user_id: int) -> str | None:
    with get_db() as conn:
        row = conn.execute("SELECT email, username FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return row["email"] or row["username"]


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


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        token = header[7:].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if not isinstance(user_id, str) or not user_id.isdigit():
                raise jwt.InvalidTokenError
            user_id = int(user_id)
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid or expired token"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    username, password = data.get("username"), data.get("password")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400
    username = username.strip()
    email = email.strip() if isinstance(email, str) else None
    with get_db() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), email),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": cursor.lastrowid, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    username, password = data.get("username"), data.get("password")
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) + JWT_LIFETIME},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return jsonify({"token": token})

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user_id):
    return jsonify(get_tasks(user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task(user_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    title = data.get("title")
    if not isinstance(title, str):
        title = ""
    title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(user_id, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(user_id, task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    previous_task = get_task(task_id, user_id)
    if previous_task is None:
        return jsonify({"error": "task not found"}), 404
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data and not isinstance(data["title"], str):
        return jsonify({"error": "title must be a string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    task = update_task(
        task_id, user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        user_email = get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


# Ensure the database is usable when the application is imported by a WSGI
# server or a test runner, not only when this module is executed as a script.
init_db()


if __name__ == "__main__":
    app.run(debug=True)
