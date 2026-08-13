"""
Flask Task Management API
SQLite-backed REST API for managing tasks with JWT authentication.
"""

from flask import Flask, request, jsonify
from functools import wraps
from datetime import datetime, timedelta
import sqlite3
import os
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from celery import Celery

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

celery_app = Celery(
    app.import_name,
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)


def get_db():
    db_path = os.environ.get("DATABASE", "tasks.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                owner_id INTEGER,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
        """)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid authorization header'}), 401

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
            current_username = data['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401

        return f(current_user_id, current_username, *args, **kwargs)

    return decorated


def get_user_by_username(username):
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,)
        ).fetchone()
    return user


def create_jwt_token(user_id, username):
    payload = {
        'user_id': user_id,
        'username': username,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "").strip()

    if not username:
        return jsonify({"error": "username is required"}), 400

    if not password:
        return jsonify({"error": "password is required"}), 400

    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    password_hash = generate_password_hash(password)

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                (username, password_hash, email if email else None)
            )
            conn.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "username already exists"}), 409

    token = create_jwt_token(user_id, username)

    return jsonify({
        "id": user_id,
        "username": username,
        "token": token
    }), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username:
        return jsonify({"error": "username is required"}), 400

    if not password:
        return jsonify({"error": "password is required"}), 400

    user = get_user_by_username(username)

    if user is None or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_jwt_token(user['id'], user['username'])

    return jsonify({
        "id": user['id'],
        "username": user['username'],
        "token": token
    }), 200


@app.route("/tasks", methods=["POST"])
@token_required
def create_task(current_user_id, current_username):
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    with get_db() as conn:
        now = datetime.utcnow().isoformat()
        cursor = conn.execute(
            "INSERT INTO tasks (title, status, created_at, owner_id) VALUES (?, ?, ?, ?)",
            (title, "pending", now, current_user_id)
        )
        conn.commit()
        task_id = cursor.lastrowid

    return jsonify({
        "id": task_id,
        "title": title,
        "status": "pending",
        "created_at": now,
        "owner_id": current_user_id
    }), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks(current_user_id, current_username):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE owner_id = ? ORDER BY created_at DESC",
            (current_user_id,)
        ).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(current_user_id, current_username, task_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ? AND owner_id = ?",
            (task_id, current_user_id)
        ).fetchone()

    if row is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(current_user_id, current_username, task_id):
    from celery_tasks import send_notification_email

    data = request.get_json(silent=True) or {}

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, owner_id FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

        if row is None:
            return jsonify({"error": "task not found"}), 404

        if row['owner_id'] != current_user_id:
            return jsonify({"error": "unauthorized"}), 403

        old_status = row['status']
        title = data.get("title")
        status = data.get("status")

        if title is not None:
            title = title.strip()
            if not title:
                return jsonify({"error": "title cannot be empty"}), 400

        if title is not None and status is not None:
            conn.execute(
                "UPDATE tasks SET title = ?, status = ? WHERE id = ?",
                (title, status, task_id)
            )
        elif title is not None:
            conn.execute(
                "UPDATE tasks SET title = ? WHERE id = ?",
                (title, task_id)
            )
        elif status is not None:
            conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id)
            )

        conn.commit()

    with get_db() as conn:
        row = conn.execute(
            "SELECT id, title, status, created_at, owner_id FROM tasks WHERE id = ?",
            (task_id,)
        ).fetchone()

    new_status = row['status']
    task_title = row['title']

    if old_status != 'completed' and new_status == 'completed':
        with get_db() as conn:
            user = conn.execute(
                "SELECT email FROM users WHERE id = ?",
                (current_user_id,)
            ).fetchone()
            if user and user['email']:
                send_notification_email.delay(user['email'], task_title)

    return jsonify(dict(row))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
