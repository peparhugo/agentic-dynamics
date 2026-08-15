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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Storage configuration
STORAGE_DIR = os.environ.get("STORAGE_DIR", "./data")
TASKS_FILE = os.path.join(STORAGE_DIR, "tasks.json")
USERS_FILE = os.path.join(STORAGE_DIR, "users.json")


# ── Storage Layer ────────────────────────────────────────────────

def _ensure_storage():
    """Ensure storage directory and file exist."""
    Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, 'w') as f:
            json.dump([], f)
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump([], f)


def _load_tasks():
    """Load all tasks from JSON file."""
    _ensure_storage()
    try:
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_tasks(tasks):
    """Save all tasks to JSON file."""
    _ensure_storage()
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)


def _get_next_id():
    """Get the next auto-increment ID."""
    tasks = _load_tasks()
    if not tasks:
        return 1
    return max(t['id'] for t in tasks) + 1


# ── User Management ──────────────────────────────────────────────

def _load_users():
    """Load all users from JSON file."""
    _ensure_storage()
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_users(users):
    """Save all users to JSON file."""
    _ensure_storage()
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)


def _get_user_by_username(username):
    """Get user by username."""
    users = _load_users()
    return next((u for u in users if u['username'] == username), None)


def _get_user_by_id(user_id):
    """Get user by ID."""
    users = _load_users()
    return next((u for u in users if u['id'] == user_id), None)


def _get_next_user_id():
    """Get the next user ID."""
    users = _load_users()
    if not users:
        return 1
    return max(u['id'] for u in users) + 1


def _create_user(username, password, email=None):
    """Create a new user with hashed password and optional email."""
    if _get_user_by_username(username):
        return None, "Username already exists"

    users = _load_users()
    new_user = {
        'id': _get_next_user_id(),
        'username': username,
        'password_hash': generate_password_hash(password),
        'email': email
    }
    users.append(new_user)
    _save_users(users)
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

    return _get_user_by_id(user_id)


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
    tasks = _load_tasks()
    users = _load_users()

    tasks_migrated = False
    if tasks and not all('owner_id' in t for t in tasks):
        default_user_id = None
        if users:
            default_user_id = users[0]['id']
        else:
            user, _ = _create_user('admin', 'admin', 'admin@example.com')
            default_user_id = user['id']

        for task in tasks:
            if 'owner_id' not in task:
                task['owner_id'] = default_user_id

        _save_tasks(tasks)
        tasks_migrated = True

    users_migrated = False
    if users and not all('email' in u for u in users):
        for user in users:
            if 'email' not in user:
                user['email'] = f"{user['username']}@example.com"
        _save_users(users)
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

    user, error = _create_user(username, password, email)
    if error:
        return jsonify({"error": error}), 409

    return jsonify({
        "id": user['id'],
        "username": user['username'],
        "email": user.get('email')
    }), 201


@app.route('/auth/login', methods=['POST'])
def login():
    """Login and get JWT token. Expects JSON: {username: str, password: str}"""
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    if not username or not password:
        return jsonify({"error": "missing username or password"}), 400

    user = _get_user_by_username(username)
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

    tasks = _load_tasks()
    new_task = {
        'id': _get_next_id(),
        'title': title,
        'status': 'pending',
        'owner_id': user['id'],
        'created_at': datetime.utcnow().isoformat()
    }
    tasks.append(new_task)
    _save_tasks(tasks)

    return jsonify(new_task), 201


@app.route('/tasks', methods=['GET'])
@_require_auth
def list_tasks(user):
    """List tasks for current user ordered by created_at descending."""
    tasks = _load_tasks()
    user_tasks = [t for t in tasks if t.get('owner_id') == user['id']]
    sorted_tasks = sorted(user_tasks, key=lambda x: x['created_at'], reverse=True)
    return jsonify(sorted_tasks)


@app.route('/tasks/<int:task_id>', methods=['GET'])
@_require_auth
def get_task(user, task_id):
    """Get a single task by ID."""
    tasks = _load_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)

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
    tasks = _load_tasks()
    task = next((t for t in tasks if t['id'] == task_id), None)

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

    _save_tasks(tasks)
    return jsonify(task)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    _ensure_storage()
    _migrate_tasks_to_add_owner()
    app.run(debug=True)
