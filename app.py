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
from repositories import UserRepository, TaskRepository

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

celery_app = Celery(
    app.import_name,
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

user_repo = UserRepository()
task_repo = TaskRepository()


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
        user_id = user_repo.create_user(username, password_hash, email if email else None)
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

    user = user_repo.get_by_username(username)

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

    now = datetime.utcnow().isoformat()
    task_id = task_repo.create_task(title, "pending", now, current_user_id)

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
    rows = task_repo.list_by_owner(current_user_id)
    return jsonify([dict(r) for r in rows])


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(current_user_id, current_username, task_id):
    row = task_repo.get_by_id(task_id, current_user_id)

    if row is None:
        return jsonify({"error": "task not found"}), 404

    return jsonify(dict(row))


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(current_user_id, current_username, task_id):
    from celery_tasks import send_notification_email

    data = request.get_json(silent=True) or {}

    row = task_repo.get_task_with_owner(task_id)

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

    task_repo.update_task(task_id, title, status)

    row = task_repo.get_by_id(task_id)

    new_status = row['status']
    task_title = row['title']

    if old_status != 'completed' and new_status == 'completed':
        user_email = user_repo.get_email_by_id(current_user_id)
        if user_email:
            send_notification_email.delay(user_email, task_title)

    return jsonify(dict(row))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
