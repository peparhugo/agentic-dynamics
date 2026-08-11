import functools
import sqlite3
import time
from datetime import datetime, timezone, timedelta

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"
DATABASE = "tasks.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at REAL NOT NULL,
            owner_id INTEGER REFERENCES users(id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def migrate_db():
    conn = get_db()
    try:
        conn.execute(
            "ALTER TABLE tasks ADD COLUMN owner_id INTEGER REFERENCES users(id)"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def row_to_dict(row):
    result = {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": datetime.fromtimestamp(row["created_at"]),
    }
    if "owner_id" in row.keys():
        result["owner_id"] = row["owner_id"]
    return result


def token_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            g.current_user_id = data["user_id"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token is invalid"}), 401

        return f(*args, **kwargs)

    return decorated


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Username already exists"}), 409

    password_hash = generate_password_hash(password)
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = jwt.encode(
        {
            "user_id": row["id"],
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        },
        app.config["SECRET_KEY"],
        algorithm="HS256",
    )

    return jsonify({"token": token})


@app.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True)
    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    title = data["title"]
    created_at = time.time()
    owner_id = g.current_user_id

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, 'pending', ?, ?)",
        (title, created_at, owner_id),
    )
    conn.commit()
    task_id = cursor.lastrowid

    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()

    return jsonify(row_to_dict(row)), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
        (g.current_user_id,),
    ).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(row_to_dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ? AND owner_id = ?",
        (task_id, g.current_user_id),
    ).fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    new_title = data.get("title", row["title"])
    new_status = data.get("status", row["status"])

    conn.execute(
        "UPDATE tasks SET title = ?, status = ? WHERE id = ? AND owner_id = ?",
        (new_title, new_status, task_id, g.current_user_id),
    )
    conn.commit()

    updated = conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()
    conn.close()

    return jsonify(row_to_dict(updated))


if __name__ == "__main__":
    init_db()
    migrate_db()
    app.run(debug=True)
