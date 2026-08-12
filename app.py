"""
Task management Flask API with JWT authentication.

Storage: a single flat JSON file (no database). The schema is
initialized on startup by creating the file if it does not exist.

Legacy flat-file data is migrated in place: existing tasks without an
``owner_id`` keep their data and are assigned ``owner_id: null``, and a
``users`` collection is added for JWT-authenticated accounts.
"""

from flask import Flask, request, jsonify, g
from datetime import datetime, timedelta, timezone
import json
import os
import threading
from functools import wraps

import jwt
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

DATA_FILE = os.environ.get("DATA_FILE", "tasks.json")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
JWT_EXPIRES_HOURS = int(os.environ.get("JWT_EXPIRES_HOURS", "24"))
_lock = threading.RLock()

app.config["SECRET_KEY"] = SECRET_KEY


def _empty_store():
    return {"tasks": [], "users": [], "next_id": 1}


def _migrate(data: dict) -> tuple[dict, bool]:
    """Bring an existing flat-file store up to the current schema.

    Returns ``(data, changed)`` where ``changed`` is True when the store
    was modified and should be written back to disk.
    """
    changed = False
    if not isinstance(data, dict):
        data = {}
        changed = True
    if "tasks" not in data:
        data["tasks"] = []
        changed = True
    if "users" not in data:
        data["users"] = []
        changed = True
    if "next_id" not in data or not isinstance(data["next_id"], int):
        data["next_id"] = 1
        changed = True
    for task in data["tasks"]:
        if not isinstance(task, dict):
            continue
        if "owner_id" not in task:
            task["owner_id"] = None
            changed = True
    return data, changed


def _read_store() -> dict:
    with _lock:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            data = _empty_store()
            _write_store(data)
            return data
        except (json.JSONDecodeError, ValueError):
            data = _empty_store()
        data, changed = _migrate(data)
        if changed:
            _write_store(data)
        return data


def _write_store(data: dict) -> None:
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, DATA_FILE)


def init_store():
    """Initialize the flat-file schema on startup."""
    _read_store()


# ── Models ────────────────────────────────────────────────────


def create_user(username: str, password: str) -> dict:
    with _lock:
        data = _read_store()
        if any(u["username"] == username for u in data["users"]):
            raise ValueError("username already taken")
        user = {
            "id": len(data["users"]) + 1,
            "username": username,
            "password_hash": generate_password_hash(password),
        }
        data["users"].append(user)
        _write_store(data)
        return {"id": user["id"], "username": user["username"]}


def get_user_by_username(username: str) -> dict | None:
    data = _read_store()
    for user in data["users"]:
        if user["username"] == username:
            return user
    return None


def get_user_by_id(user_id: int) -> dict | None:
    data = _read_store()
    for user in data["users"]:
        if user["id"] == user_id:
            return user
    return None


def verify_user(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if user is None:
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return {"id": user["id"], "username": user["username"]}


def create_task(title: str, owner_id: int) -> dict:
    with _lock:
        data = _read_store()
        task = {
            "id": data["next_id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "owner_id": owner_id,
        }
        data["tasks"].append(task)
        data["next_id"] += 1
        _write_store(data)
        return task


def get_tasks(owner_id: int):
    data = _read_store()
    tasks = [t for t in data["tasks"] if t.get("owner_id") == owner_id]
    return sorted(tasks, key=lambda t: t["created_at"], reverse=True)


def get_task(task_id: int, owner_id: int) -> dict | None:
    data = _read_store()
    for task in data["tasks"]:
        if task["id"] == task_id and task.get("owner_id") == owner_id:
            return task
    return None


def update_task(
    task_id: int, owner_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    with _lock:
        data = _read_store()
        for task in data["tasks"]:
            if task["id"] == task_id and task.get("owner_id") == owner_id:
                if title is not None:
                    task["title"] = title
                if status is not None:
                    task["status"] = status
                _write_store(data)
                return task
        return None


# ── Auth ──────────────────────────────────────────────────────


def _generate_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != "Bearer":
            return jsonify({"error": "missing or invalid token"}), 401
        token = parts[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.PyJWTError:
            return jsonify({"error": "missing or invalid token"}), 401
        g.user_id = payload.get("sub")
        g.username = payload.get("username")
        if g.user_id is None or get_user_by_id(g.user_id) is None:
            return jsonify({"error": "missing or invalid token"}), 401
        return f(*args, **kwargs)

    return wrapper


# ── Routes: auth ──────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if username is None or not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if password is None or not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    username = username.strip()
    try:
        user = create_user(username, password)
    except ValueError:
        return jsonify({"error": "username already taken"}), 409
    return jsonify(user), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "username and password are required"}), 400
    user = verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    token = _generate_token(user)
    return jsonify({"token": token, "username": user["username"], "id": user["id"]})


# ── Routes: tasks (protected) ─────────────────────────────────

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if title is None or not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = create_task(title.strip(), g.user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    status = data.get("status")
    if title is not None and not isinstance(title, str):
        return jsonify({"error": "title must be a string"}), 400
    task = update_task(task_id, g.user_id, title=title, status=status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_store()
    app.run(debug=True)
