"""
Flask Task Management API with flat-file storage.
Uses JSON files for persistence instead of databases.
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from functools import wraps
import json
import os
from pathlib import Path
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
app.config["JWT_ALGORITHM"] = "HS256"
app.config["JWT_EXPIRATION_HOURS"] = 24

DATA_DIR = os.environ.get("DATA_DIR", "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")


# ── Storage initialization ──────────────────────────────────────

def get_data_dir():
    """Get the data directory, supporting dynamic monkeypatch in tests."""
    import app as app_module
    return app_module.DATA_DIR


def get_tasks_file():
    """Get the tasks file path, supporting dynamic monkeypatch in tests."""
    import app as app_module
    return app_module.TASKS_FILE


def get_users_file():
    """Get the users file path, supporting dynamic monkeypatch in tests."""
    import app as app_module
    return app_module.USERS_FILE


def ensure_data_dir():
    data_dir = get_data_dir()
    Path(data_dir).mkdir(exist_ok=True)


def init_tasks_file():
    ensure_data_dir()
    tasks_file = get_tasks_file()
    if not os.path.exists(tasks_file):
        with open(tasks_file, "w") as f:
            json.dump({"tasks": [], "next_id": 1}, f)


def init_users_file():
    ensure_data_dir()
    users_file = get_users_file()
    if not os.path.exists(users_file):
        with open(users_file, "w") as f:
            json.dump({"users": [], "next_id": 1}, f)


def load_tasks():
    init_tasks_file()
    tasks_file = get_tasks_file()
    with open(tasks_file, "r") as f:
        data = json.load(f)
    return data


def save_tasks(data):
    tasks_file = get_tasks_file()
    with open(tasks_file, "w") as f:
        json.dump(data, f, indent=2)


def load_users():
    init_users_file()
    users_file = get_users_file()
    with open(users_file, "r") as f:
        data = json.load(f)
    return data


def save_users(data):
    users_file = get_users_file()
    with open(users_file, "w") as f:
        json.dump(data, f, indent=2)


def migrate_tasks_add_owner():
    """Add owner_id to existing tasks that don't have it."""
    tasks_data = load_tasks()
    users_data = load_users()

    if users_data["users"]:
        default_owner_id = users_data["users"][0]["id"]
        modified = False
        for task in tasks_data["tasks"]:
            if "owner_id" not in task:
                task["owner_id"] = default_owner_id
                modified = True
        if modified:
            save_tasks(tasks_data)


# ── Authentication ─────────────────────────────────────────────

def generate_token(user_id):
    """Generate a JWT token for a user."""
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=app.config["JWT_EXPIRATION_HOURS"])
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])


def verify_token(token):
    """Verify a JWT token and return the user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=[app.config["JWT_ALGORITHM"]])
        return payload.get("user_id")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def token_required(f):
    """Decorator to require a valid JWT token in Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]

        if not token:
            return jsonify({"error": "missing or invalid authorization header"}), 401

        user_id = verify_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401

        return f(user_id, *args, **kwargs)

    return decorated


# ── Endpoints ───────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    """Register a new user. Requires 'username' and 'password' in JSON body."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    users_data = load_users()

    if any(u["username"] == username for u in users_data["users"]):
        return jsonify({"error": "username already exists"}), 409

    user_id = users_data["next_id"]
    new_user = {
        "id": user_id,
        "username": username,
        "password_hash": generate_password_hash(password),
        "created_at": datetime.utcnow().isoformat()
    }

    users_data["users"].append(new_user)
    users_data["next_id"] = user_id + 1
    save_users(users_data)

    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    """Login a user. Requires 'username' and 'password' in JSON body. Returns JWT token."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    users_data = load_users()
    user = next((u for u in users_data["users"] if u["username"] == username), None)

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401

    token = generate_token(user["id"])
    return jsonify({"token": token}), 200


@app.route("/tasks", methods=["POST"])
@token_required
def create_task(user_id):
    """Create a new task. Requires 'title' in JSON body and valid JWT."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()

    if not title:
        return jsonify({"error": "title is required"}), 400

    tasks_data = load_tasks()
    task_id = tasks_data["next_id"]

    new_task = {
        "id": task_id,
        "title": title,
        "status": "pending",
        "owner_id": user_id,
        "created_at": datetime.utcnow().isoformat()
    }

    tasks_data["tasks"].append(new_task)
    tasks_data["next_id"] = task_id + 1
    save_tasks(tasks_data)

    return jsonify(new_task), 201


@app.route("/tasks", methods=["GET"])
@token_required
def list_tasks(user_id):
    """List all tasks for the current user, ordered by created_at descending."""
    tasks_data = load_tasks()
    user_tasks = [t for t in tasks_data["tasks"] if t.get("owner_id") == user_id]
    sorted_tasks = sorted(user_tasks, key=lambda t: t["created_at"], reverse=True)
    return jsonify(sorted_tasks), 200


@app.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(user_id, task_id):
    """Get a single task by ID. User can only access their own tasks."""
    tasks_data = load_tasks()
    task = next((t for t in tasks_data["tasks"] if t["id"] == task_id), None)

    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.get("owner_id") != user_id:
        return jsonify({"error": "unauthorized"}), 403

    return jsonify(task), 200


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(user_id, task_id):
    """Update a task's title and/or status. User can only update their own tasks."""
    data = request.get_json(silent=True) or {}
    tasks_data = load_tasks()

    task = next((t for t in tasks_data["tasks"] if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    if task.get("owner_id") != user_id:
        return jsonify({"error": "unauthorized"}), 403

    if "title" in data:
        title = data["title"]
        if isinstance(title, str):
            title = title.strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        task["title"] = title

    if "status" in data:
        task["status"] = data["status"]

    save_tasks(tasks_data)
    return jsonify(task), 200


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    init_tasks_file()
    init_users_file()
    migrate_tasks_add_owner()
    app.run(debug=True)
