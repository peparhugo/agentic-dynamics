"""
Flask task management API with SQLite storage.

Models: User (id, username, password_hash), Task (id, title, status, created_at, owner_id)
Status values: 'pending' (default) or 'done'
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "tasks.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
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
            "  username TEXT UNIQUE NOT NULL,"
            "  password_hash TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT NOT NULL,"
            "  status TEXT NOT NULL DEFAULT 'pending',"
            "  created_at TEXT NOT NULL,"
            "  owner_id INTEGER,"
            "  FOREIGN KEY (owner_id) REFERENCES users(id)"
            ")"
        )
        conn.commit()
        migrate_tasks_add_owner()


def migrate_tasks_add_owner():
    """Migrate existing tasks without owner_id to have owner_id = NULL."""
    with get_db() as conn:
        cursor = conn.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]
        if "owner_id" not in columns:
            conn.execute("ALTER TABLE tasks ADD COLUMN owner_id INTEGER")
            conn.commit()


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"error": "Invalid token format"}), 401

        if not token:
            return jsonify({"error": "Missing token"}), 401

        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            user_id = data.get("user_id")
            if user_id is None:
                return jsonify({"error": "Invalid token"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(user_id, *args, **kwargs)
    return decorated


def create_user(username: str, password: str) -> dict | None:
    password_hash = generate_password_hash(password)
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            conn.commit()
            return {"id": cursor.lastrowid, "username": username}
    except sqlite3.IntegrityError:
        return None


def verify_user(username: str, password: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            return {"id": row["id"], "username": row["username"]}
    return None


def create_task(title: str, owner_id: int) -> dict:
    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, "pending", now, owner_id),
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
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int, owner_id: int):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, owner_id),
        ).fetchone()
        return dict(row) if row else None


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None):
    task = get_task(task_id, owner_id)
    if task is None:
        return None

    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

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
            params.append(task_id)
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()
    return get_task(task_id, owner_id)


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = create_user(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401

    token = jwt.encode(
        {
            "user_id": user["id"],
            "username": user["username"],
            "exp": datetime.utcnow() + timedelta(hours=24),
        },
        SECRET_KEY,
        algorithm="HS256",
    )
    return jsonify({"token": token})


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks(user_id):
    return jsonify(get_tasks(user_id))


@app.route("/tasks", methods=["POST"])
@token_required
def add_task(user_id):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def show_task(user_id, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def edit_task(user_id, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "status" in data and data["status"] not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status: {data['status']}"}), 422

    updated_task = update_task(
        task_id,
        user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    return jsonify(updated_task)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
