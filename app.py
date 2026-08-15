"""
Flask Todo API — flat-file storage with JWT authentication.

A single-file Flask app with clean structure: models, routes, error handling.
All data is stored in a JSON flat file (no databases).

Endpoints:
  POST /auth/register   -> create a user
  POST /auth/login      -> issue a JWT
  /tasks/*              -> require a valid JWT (owner-scoped)
"""

import functools
import json
import os
import threading
from datetime import datetime, timedelta

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "dev-secret-key-for-local-development-only"
)

DATA_FILE = os.environ.get("DATA_FILE", "tasks.json")
TOKEN_TTL = timedelta(hours=12)
_lock = threading.Lock()


def _read() -> dict:
    with open(DATA_FILE) as f:
        return json.load(f)


def _write(store: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(store, f, indent=2)


def init_store() -> None:
    with _lock:
        if not os.path.exists(DATA_FILE):
            _write({"tasks": [], "next_id": 1, "users": [], "next_user_id": 1})
        else:
            store = _read()
            if _migrate(store):
                _write(store)


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
                "password_hash": generate_password_hash("legacy"),
            }
            store["next_user_id"] += 1
            store["users"].append(legacy)
        for task in ownerless:
            task["owner_id"] = legacy["id"]
        changed = True
    return changed


# ── Models: Users ──────────────────────────────────────────────

def create_user(username: str, password: str) -> dict:
    with _lock:
        store = _read()
        if any(u["username"] == username for u in store["users"]):
            return None
        user = {
            "id": store["next_user_id"],
            "username": username,
            "password_hash": generate_password_hash(password),
        }
        store["next_user_id"] += 1
        store["users"].append(user)
        _write(store)
        return user


def get_user_by_username(username: str) -> dict | None:
    store = _read()
    for user in store["users"]:
        if user["username"] == username:
            return user
    return None


def get_user(user_id: int) -> dict | None:
    store = _read()
    for user in store["users"]:
        if user["id"] == user_id:
            return user
    return None


def verify_user(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return None
    return user


# ── Models: Tasks ──────────────────────────────────────────────

def create_task(title: str, owner_id: int) -> dict:
    with _lock:
        store = _read()
        task = {
            "id": store["next_id"],
            "title": title,
            "status": "pending",
            "owner_id": owner_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        store["tasks"].append(task)
        store["next_id"] += 1
        _write(store)
        return task


def get_tasks(owner_id: int) -> list:
    store = _read()
    mine = [t for t in store["tasks"] if t.get("owner_id") == owner_id]
    return sorted(mine, key=lambda t: t["created_at"], reverse=True)


def get_task(task_id: int, owner_id: int) -> dict | None:
    store = _read()
    for task in store["tasks"]:
        if task["id"] == task_id and task.get("owner_id") == owner_id:
            return task
    return None


def update_task(
    task_id: int,
    owner_id: int,
    title: str | None = None,
    status: str | None = None,
) -> dict | None:
    with _lock:
        store = _read()
        for task in store["tasks"]:
            if task["id"] == task_id and task.get("owner_id") == owner_id:
                if title is not None:
                    task["title"] = title
                if status is not None:
                    task["status"] = status
                _write(store)
                return task
    return None


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
        user = get_user(int(payload.get("sub")))
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
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "username is required"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "password is required"}), 400
    user = create_user(username.strip(), password)
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
    user = verify_user(username, password)
    if user is None:
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": token_for(user)})


# ── Routes: Tasks ──────────────────────────────────────────────

@app.route("/tasks", methods=["GET"])
@auth_required
def list_tasks():
    return jsonify(get_tasks(g.current_user["id"]))


@app.route("/tasks", methods=["POST"])
@auth_required
def add_task():
    data = request.get_json(silent=True) or {}
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    task = create_task(title.strip(), g.current_user["id"])
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@auth_required
def show_task(task_id: int):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@auth_required
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    task = update_task(
        task_id,
        g.current_user["id"],
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


if __name__ == "__main__":
    init_store()
    app.run(debug=True)
