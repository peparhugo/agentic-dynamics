import json
import os
import secrets
import threading
from datetime import datetime, timedelta
from functools import wraps

import bcrypt
import jwt
from flask import Flask, jsonify, request

app = Flask(__name__)
app.config["STORAGE_FILE"] = os.environ.get("TASKS_DB", "tasks.json")
app.config["USERS_FILE"] = os.environ.get("USERS_DB", "users.json")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["JWT_ALGORITHM"] = "HS256"

TOKEN_TTL_SECONDS = int(os.environ.get("TOKEN_TTL", "3600"))

_lock = threading.Lock()


def storage_file():
    return app.config["STORAGE_FILE"]


def users_file():
    return app.config["USERS_FILE"]


def init_storage():
    with _lock:
        if not os.path.exists(storage_file()):
            _write_tasks([])
        if not os.path.exists(users_file()):
            _write_users([])
    migrate_storage()


def _read_tasks():
    path = storage_file()
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def _write_tasks(tasks):
    with open(storage_file(), "w") as f:
        json.dump(tasks, f)


def _read_users():
    path = users_file()
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def _write_users(users):
    with open(users_file(), "w") as f:
        json.dump(users, f)


def _next_id(items):
    return max((i["id"] for i in items), default=0) + 1


def _find_task(tasks, task_id):
    return next((t for t in tasks if t["id"] == task_id), None)


def _find_user_by_username(users, username):
    return next((u for u in users if u["username"] == username), None)


def _find_user_by_id(users, user_id):
    return next((u for u in users if u["id"] == user_id), None)


def hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def migrate_storage():
    with _lock:
        tasks = _read_tasks()
        legacy_ids = [t["id"] for t in tasks if t.get("owner_id") is None]
        if not legacy_ids:
            return
        users = _read_users()
        legacy_user = _find_user_by_username(users, "legacy")
        if legacy_user is None:
            legacy_user = {
                "id": _next_id(users),
                "username": "legacy",
                "password_hash": hash_password(secrets.token_hex(16)),
                "created_at": datetime.utcnow().isoformat(),
            }
            users.append(legacy_user)
            _write_users(users)
        for task in tasks:
            if task["id"] in legacy_ids:
                task["owner_id"] = legacy_user["id"]
        _write_tasks(tasks)


def create_token(user_id, username):
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(seconds=TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])


def get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, app.config["SECRET_KEY"], algorithms=[app.config["JWT_ALGORITHM"]]
        )
    except jwt.InvalidTokenError:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    with _lock:
        return _find_user_by_id(_read_users(), user_id)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        return f(user, *args, **kwargs)

    return decorated


@app.route("/auth/register", methods=["POST"])
def register():
    init_storage()
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    with _lock:
        users = _read_users()
        if _find_user_by_username(users, username) is not None:
            return jsonify({"error": "username already taken"}), 409
        user = {
            "id": _next_id(users),
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.utcnow().isoformat(),
        }
        users.append(user)
        _write_users(users)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    init_storage()
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400
    with _lock:
        user = _find_user_by_username(_read_users(), username)
    if user is None or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "invalid credentials"}), 401
    token = create_token(user["id"], user["username"])
    return jsonify({"token": token, "username": user["username"]})


@app.route("/tasks", methods=["POST"])
@require_auth
def create_task(user):
    init_storage()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    with _lock:
        tasks = _read_tasks()
        task = {
            "id": _next_id(tasks),
            "owner_id": user["id"],
            "title": title,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        tasks.append(task)
        _write_tasks(tasks)
    return jsonify(task), 201


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user):
    init_storage()
    with _lock:
        tasks = _read_tasks()
    tasks = [t for t in tasks if t.get("owner_id") == user["id"]]
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return jsonify(tasks)


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def get_task(user, task_id):
    init_storage()
    with _lock:
        task = _find_task(_read_tasks(), task_id)
    if task is None or task.get("owner_id") != user["id"]:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def update_task(user, task_id):
    init_storage()
    data = request.get_json(silent=True) or {}
    with _lock:
        tasks = _read_tasks()
        task = _find_task(tasks, task_id)
        if task is None or task.get("owner_id") != user["id"]:
            return jsonify({"error": "task not found"}), 404
        if "title" in data:
            title = (data.get("title") or "").strip()
            if not title:
                return jsonify({"error": "title is required"}), 400
            task["title"] = title
        if "status" in data:
            status = (data.get("status") or "").strip()
            if not status:
                return jsonify({"error": "status is required"}), 400
            task["status"] = status
        _write_tasks(tasks)
    return jsonify(task)


if __name__ == "__main__":
    init_storage()
    app.run(debug=True)
