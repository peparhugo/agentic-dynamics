"""
Task Management Flask API using flat-file storage (JSON).
"""

from flask import Flask, request, jsonify
from functools import wraps
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from celery_tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Storage configuration
STORAGE_DIR = os.environ.get("STORAGE_DIR", "./data")
TASKS_FILE = os.path.join(STORAGE_DIR, "tasks.json")
USERS_FILE = os.path.join(STORAGE_DIR, "users.json")


def _get_storage_dir():
    """Get current storage directory (for test patching support)."""
    import sys
    module = sys.modules[__name__]
    return module.STORAGE_DIR


# Initialize repositories
task_repo = TaskRepository(_get_storage_dir)
user_repo = UserRepository(_get_storage_dir)


# ── Storage Layer (delegating to repositories) ────────────────────────────────────────────────

def _ensure_storage():
    """Ensure storage directory and file exist."""
    task_repo._ensure_storage()
    user_repo._ensure_storage()


def _load_tasks():
    """Load all tasks from JSON file."""
    return task_repo.get_all()


def _save_tasks(tasks):
    """Save all tasks to JSON file."""
    task_repo._save_all(tasks)


def _get_next_id():
    """Get the next auto-increment ID."""
    return task_repo.get_next_id()


# ── User Management (delegating to repositories) ──────────────────────────

def _load_users():
    """Load all users from JSON file."""
    return user_repo.get_all()


def _save_users(users):
    """Save all users to JSON file."""
    user_repo._save_all(users)


def _get_user_by_username(username):
    """Get user by username."""
    return user_repo.get_by_username(username)


def _get_user_by_id(user_id):
    """Get user by ID."""
    return user_repo.get_by_id(user_id)


def _get_next_user_id():
    """Get the next user ID."""
    return user_repo.get_next_id()


def _create_user(username, password, email=None):
    """Create a new user with hashed password and optional email."""
    if user_repo.get_by_username(username):
        return None, "Username already exists"

    new_user = {
        'id': user_repo.get_next_id(),
        'username': username,
        'password_hash': generate_password_hash(password),
        'email': email
    }
    user_repo.create(new_user)
    return new_user, None


def _generate_token(user_id):
    """Generate a JWT token for a user."""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')


def _verify_token(token):
    """Verify a JWT token and return user_id if valid."""
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def _get_auth_user():
    """Get authenticated user from request."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    user_id = _verify_token(token)
    if user_id is None:
        return None

    return user_repo.get_by_id(user_id)


def _require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = _get_auth_user()
        if user is None:
            return jsonify({"error": "missing or invalid token"}), 401
        return f(user, *args, **kwargs)
    return decorated_function


def _migrate_tasks_to_add_owner():
    """Migrate existing tasks to have owner_id and add email field to users."""
    tasks = task_repo.get_all()
    users = user_repo.get_all()

    tasks_migrated = False
    if tasks and not all('owner_id' in t for t in tasks):
        default_user_id = None
        if users:
            default_user_id = users[0]['id']
        else:
            new_user = {
                'id': user_repo.get_next_id(),
                'username': 'admin',
                'password_hash': generate_password_hash('admin'),
                'email': 'admin@example.com'
            }
            user_repo.create(new_user)
            default_user_id = new_user['id']

        for task in tasks:
            if 'owner_id' not in task:
                task['owner_id'] = default_user_id

        task_repo._save_all(tasks)
        tasks_migrated = True

    users_migrated = False
    if users and not all('email' in u for u in users):
        for user in users:
            if 'email' not in user:
                user['email'] = f"{user['username']}@example.com"
        user_repo._save_all(users)
        users_migrated = True

    return tasks_migrated or users_migrated


# ── Endpoints ────────────────────────────────────────────────────

@app.route('/auth/register', methods=['POST'])
def register():
    """Register a new user. Expects JSON: {username: str, password: str, email?: str}"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip() or None

    if not username or not password:
        return jsonify({"error": "missing username or password"}), 400

    if user_repo.get_by_username(username):
        return jsonify({"error": "Username already exists"}), 409

    new_user = {
        'id': user_repo.get_next_id(),
        'username': username,
        'password_hash': generate_password_hash(password),
        'email': email
    }
    user_repo.create(new_user)

    return jsonify({
        "id": new_user['id'],
        "username": new_user['username'],
        "email": new_user.get('email')
    }), 201


@app.route('/auth/login', methods=['POST'])
def login():
    """Login and get JWT token. Expects JSON: {username: str, password: str}"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"error": "missing username or password"}), 400

    user = user_repo.get_by_username(username)
    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "invalid username or password"}), 401

    token = _generate_token(user['id'])
    return jsonify({"token": token}), 200


@app.route('/tasks', methods=['POST'])
@_require_auth
def create_task(user):
    """Create a new task. Expects JSON: {title: str}"""
    data = request.get_json(silent=True) or {}
    title = data.get('title', '').strip()

    if not title:
        return jsonify({"error": "missing title"}), 400

    new_task = {
        'id': task_repo.get_next_id(),
        'title': title,
        'status': 'pending',
        'owner_id': user['id'],
        'created_at': datetime.utcnow().isoformat()
    }
    task_repo.create(new_task)

    return jsonify(new_task), 201


@app.route('/tasks', methods=['GET'])
@_require_auth
def list_tasks(user):
    """List tasks for current user ordered by created_at descending."""
    user_tasks = task_repo.get_by_owner(user['id'])
    sorted_tasks = sorted(user_tasks, key=lambda x: x['created_at'], reverse=True)
    return jsonify(sorted_tasks)


@app.route('/tasks/<int:task_id>', methods=['GET'])
@_require_auth
def get_task(user, task_id):
    """Get a single task by ID."""
    task = task_repo.get_by_id(task_id)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.get('owner_id') != user['id']:
        return jsonify({"error": "task not found"}), 404

    return jsonify(task)


@app.route('/tasks/<int:task_id>', methods=['PUT'])
@_require_auth
def update_task(user, task_id):
    """Update task title and/or status."""
    data = request.get_json(silent=True) or {}
    task = task_repo.get_by_id(task_id)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.get('owner_id') != user['id']:
        return jsonify({"error": "task not found"}), 404

    # Update title if provided
    if 'title' in data:
        title = data['title'].strip()
        if title:
            task['title'] = title

    # Update status if provided and trigger notification if completed
    if 'status' in data:
        old_status = task.get('status')
        new_status = data['status']
        task['status'] = new_status

        # Trigger email notification asynchronously when task is completed
        if new_status == 'completed' and old_status != 'completed':
            user_email = user.get('email')
            if user_email:
                send_notification_email.delay(user_email, task['title'])

    task_repo.update(task_id, task)
    return jsonify(task)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    _ensure_storage()
    _migrate_tasks_to_add_owner()
    app.run(debug=True)
