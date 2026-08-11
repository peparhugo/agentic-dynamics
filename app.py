import functools
import sqlite3
from datetime import datetime, timezone, timedelta

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from celery_config import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"
DATABASE = "tasks.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


task_repo = TaskRepository(get_db)
user_repo = UserRepository(get_db)


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

    existing = user_repo.find_by_username(username)
    if existing:
        return jsonify({"error": "Username already exists"}), 409

    password_hash = generate_password_hash(password)
    user_id = user_repo.create(username, password_hash)

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

    row = user_repo.find_by_username(username)

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
    owner_id = g.current_user_id

    task = task_repo.create(title=title, owner_id=owner_id)

    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    tasks = task_repo.find_all_by_owner(g.current_user_id)
    return jsonify(tasks)


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    task = task_repo.find_by_id_and_owner(task_id, g.current_user_id)

    if task is None:
        return jsonify({"error": "Task not found"}), 404

    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    existing = task_repo.find_by_id_and_owner(task_id, g.current_user_id)

    if existing is None:
        return jsonify({"error": "Task not found"}), 404

    new_title = data.get("title", existing["title"])
    new_status = data.get("status", existing["status"])

    updated = task_repo.update(task_id, g.current_user_id, new_title, new_status)

    if new_status == "completed":
        user_row = user_repo.find_username_by_id(g.current_user_id)
        if user_row:
            user_email = f"{user_row['username']}@example.com"
            send_notification_email.delay(user_email, new_title)

    return jsonify(updated)


if __name__ == "__main__":
    init_db()
    migrate_db()
    app.run(debug=True)
