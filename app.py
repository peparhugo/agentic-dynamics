"""Flask task-management API backed by a JSON flat file."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

# Kept configurable so deployments and tests can use an isolated data file.
DATABASE = os.environ.get("DATABASE", "tasks.json")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_EXPIRATION_HOURS = 24


def _empty_store() -> dict:
    return {"next_id": 1, "next_user_id": 1, "tasks": [], "users": []}


def init_db() -> None:
    """Create and migrate the flat-file schema without discarding stored tasks."""
    path = Path(DATABASE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        _write_store(_empty_store())
        return

    with path.open(encoding="utf-8") as data_file:
        store = json.load(data_file)
    changed = False
    if "users" not in store:
        store["users"] = []
        changed = True
    if "next_user_id" not in store:
        store["next_user_id"] = max((user["id"] for user in store["users"]), default=0) + 1
        changed = True
    # Pre-authentication tasks remain intact but have no owner and are inaccessible.
    for task in store.get("tasks", []):
        if "owner_id" not in task:
            task["owner_id"] = None
            changed = True
    if changed:
        _write_store(store)


def _read_store() -> dict:
    init_db()
    with Path(DATABASE).open(encoding="utf-8") as data_file:
        return json.load(data_file)


def _write_store(store: dict) -> None:
    path = Path(DATABASE)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8") as data_file:
        json.dump(store, data_file)
    temporary_path.replace(path)


def create_task(title: str, owner_id: int) -> dict:
    store = _read_store()
    task = {
        "id": store["next_id"],
        "title": title,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": owner_id,
    }
    store["next_id"] += 1
    store["tasks"].append(task)
    _write_store(store)
    return task


def get_tasks(owner_id: int) -> list[dict]:
    tasks = [task for task in _read_store()["tasks"] if task["owner_id"] == owner_id]
    return sorted(tasks, key=lambda task: task["created_at"], reverse=True)


def get_task(task_id: int, owner_id: int) -> dict | None:
    for task in _read_store()["tasks"]:
        if task["id"] == task_id and task["owner_id"] == owner_id:
            return task
    return None


def update_task(
    task_id: int, owner_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    store = _read_store()
    for task in store["tasks"]:
        if task["id"] == task_id and task["owner_id"] == owner_id:
            if title is not None:
                task["title"] = title
            if status is not None:
                task["status"] = status
            _write_store(store)
            return task
    return None


def _json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _encode_token(user_id: int) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)).timestamp()),
    }
    encoded_header = _base64url(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _base64url(json.dumps(payload, separators=(",", ":")).encode())
    signed_data = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(JWT_SECRET.encode(), signed_data.encode(), hashlib.sha256).digest()
    return f"{signed_data}.{_base64url(signature)}"


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode_token(token: str) -> int | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signed_data = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            JWT_SECRET.encode(), signed_data.encode(), hashlib.sha256
        ).digest()
        supplied_signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected_signature, supplied_signature):
            return None
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, int) or payload.get("exp", 0) < datetime.now(timezone.utc).timestamp():
            return None
        return user_id
    except (AttributeError, UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _get_user(username: str) -> dict | None:
    return next((user for user in _read_store()["users"] if user["username"] == username), None)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        user_id = _decode_token(token) if scheme == "Bearer" and token else None
        if user_id is None or not any(user["id"] == user_id for user in _read_store()["users"]):
            return jsonify({"error": "unauthorized"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


@app.route("/auth/register", methods=["POST"])
def register():
    data = _json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    store = _read_store()
    if any(user["username"] == username for user in store["users"]):
        return jsonify({"error": "username already exists"}), 409
    user = {
        "id": store["next_user_id"],
        "username": username,
        "password_hash": generate_password_hash(password),
    }
    store["next_user_id"] += 1
    store["users"].append(user)
    _write_store(store)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = _json_body()
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"error": "invalid credentials"}), 401
    user = _get_user(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": _encode_token(user["id"])})


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user_id: int):
    return jsonify(get_tasks(user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task(user_id: int):
    data = _json_body()
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    task = create_task(title.strip(), user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(user_id: int, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(user_id: int, task_id: int):
    data = _json_body()
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400

    title = data.get("title")
    status = data.get("status")
    if "title" in data and (not isinstance(title, str) or not title.strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400

    task = update_task(task_id, user_id, title.strip() if title is not None else None, status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
