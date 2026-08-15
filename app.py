"""
Flask Todo API — flat-file storage with JWT authentication.

A single-file Flask app with clean structure: routes and error handling,
backed by a repository data-access layer. All data is stored in a JSON
flat file (no databases).

Endpoints:
  POST /auth/register   -> create a user
  POST /auth/login      -> issue a JWT
  /tasks/*              -> require a valid JWT (owner-scoped)
"""

import functools
import os
import threading
from datetime import datetime, timedelta

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import generate_password_hash

from email_tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-secret-key-for-local-development-only"
)

DATA_FILE = os.environ.get("DATA_FILE", "tasks.json")
TOKEN_TTL = timedelta(hours=12)
_lock = threading.Lock()

task_repo = TaskRepository(data_file=lambda: DATA_FILE, lock=_lock)
user_repo = UserRepository(data_file=lambda: DATA_FILE, lock=_lock)


def init_store() -> None:
    with _lock:
        if not os.path.exists(DATA_FILE):
            user_repo.write_store(
                {"tasks": [], "next_id": 1, "users": [], "next_user_id": 1}
            )
        else:
            store = user_repo.read_store()
            if _migrate(store):
                user_repo.write_store(store)


def _migrate(store: dict) -> bool:
    """Bring old stores up to date without destroying existing data."""
    changed = False
    if "users" not in store:
        store["users"] = []
        changed = True
    if "next_user_id" not in store:
        store["next_user_id"] = 1
        changed = True

    ownerless = [
        t for t in store.get("tasks", [])
        if t.get("owner_id") is None
    ]
    if ownerless:
        legacy = next(
            (u for u in store["users"] if u["username"] == "legacy"), None
        )
        if legacy is None:
            legacy = {
                "id": store["next_user_id"],
                "username": "legacy",
                "email": "legacy@example.com",
                "password_hash": generate_password_hash("legacy"),
            }
            store["next_user_id"] += 1
            store["users"].append(legacy)
        for task in ownerless:
            task["owner_id"] = legacy["id"]
        changed = True
    return changed


# ── Auth helpers ───────────────────────────────────────────────

def token_for(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "exp": datetime.utcnow() + TOKEN_TTL,
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def auth_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
        if not token:
            return jsonify({"error": "missing or invalid token"}), 401
        try:
            payload = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=["HS256"]
            )
        except jwt.PyJWTError:
            return jsonify({"error": "missing or invalid token"}), 401
        user = user_repo.get(int(payload.get("sub")))
        if user is None:
            return jsonify({"error": "missing or invalid token"}), 401
        g.current_user = user
        return func(*args, **kwargs)

    return wrapper


# ── Routes: Auth ───────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    user = user_repo.create_user(username.strip(), password, email=email)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"], "token": token_for(user)}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "username and password are required"}), 400
    user = user_repo.verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": token_for(user)})


# ── Routes: Tasks ──────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks():
    return jsonify(task_repo.list_for_owner(g.current_user["id"]))


@app.route("/tasks", methods=["POST"])
@auth_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = task_repo.create_task(title.strip(), g.current_user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def show_task(task_id: int):
    task = task_repo.get_for_owner(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    current = task_repo.get_for_owner(task_id, g.current_user["id"])
    if current is None:
        return jsonify({"error": "task not found"}), 404
    task = task_repo.update(
        task_id,
        g.current_user["id"],
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if task["status"] == "completed" and current["status"] != "completed":
        user = g.current_user
        user_email = user.get("email") or f"{user['username']}@example.com"
        send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


if __name__ == "__main__":
    init_store()
    app.run(debug=True)
