"""Flask task management API backed by JSON flat files."""

import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

# Tests or deployments may override this path. User data lives alongside task data.
DATA_FILE = os.environ.get("TASKS_FILE", "tasks.json")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
TOKEN_LIFETIME_SECONDS = 3600


def _data_path() -> Path:
    return Path(DATA_FILE)


def _users_path() -> Path:
    return _data_path().with_name("users.json")


def _read_json_list(path: Path, description: str) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{description} contains invalid JSON") from error
    if not isinstance(data, list):
        raise RuntimeError(f"{description} must contain a JSON list")
    return data


def _write_json_list(path: Path, items: list[dict]) -> None:
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(items, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def init_db() -> None:
    """Create stores and migrate existing task records to include ownership."""
    task_path = _data_path()
    task_path.parent.mkdir(parents=True, exist_ok=True)
    if not task_path.exists():
        task_path.write_text("[]\n", encoding="utf-8")
    if not _users_path().exists():
        _users_path().write_text("[]\n", encoding="utf-8")

    tasks = _read_json_list(task_path, "task storage")
    # Existing tasks have no safely inferable owner, so retain them as unowned.
    if any("owner_id" not in task for task in tasks):
        for task in tasks:
            task.setdefault("owner_id", None)
        _write_json_list(task_path, tasks)


def _read_tasks() -> list[dict]:
    init_db()
    return _read_json_list(_data_path(), "task storage")


def _write_tasks(tasks: list[dict]) -> None:
    _write_json_list(_data_path(), tasks)


def _read_users() -> list[dict]:
    init_db()
    return _read_json_list(_users_path(), "user storage")


def _write_users(users: list[dict]) -> None:
    _write_json_list(_users_path(), users)


def create_user(username: str, password: str) -> dict | None:
    users = _read_users()
    if any(user["username"] == username for user in users):
        return None
    user = {
        "id": max((user["id"] for user in users), default=0) + 1,
        "username": username,
        "password_hash": generate_password_hash(password),
    }
    users.append(user)
    _write_users(users)
    return user


def get_user_by_username(username: str) -> dict | None:
    return next((user for user in _read_users() if user["username"] == username), None)


def get_user_by_id(user_id: int) -> dict | None:
    return next((user for user in _read_users() if user["id"] == user_id), None)


def create_task(title: str, owner_id: int) -> dict:
    tasks = _read_tasks()
    task = {
        "id": max((task["id"] for task in tasks), default=0) + 1,
        "title": title,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": owner_id,
    }
    tasks.append(task)
    _write_tasks(tasks)
    return task


def get_tasks(owner_id: int) -> list[dict]:
    tasks = (task for task in _read_tasks() if task.get("owner_id") == owner_id)
    return sorted(tasks, key=lambda task: task["created_at"], reverse=True)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return next(
        (task for task in _read_tasks() if task["id"] == task_id and task.get("owner_id") == owner_id),
        None,
    )


def update_task(
    task_id: int, owner_id: int, title: str | None = None, status: str | None = None
) -> dict | None:
    tasks = _read_tasks()
    task = next(
        (item for item in tasks if item["id"] == task_id and item.get("owner_id") == owner_id),
        None,
    )
    if task is None:
        return None
    if title is not None:
        task["title"] = title
    if status is not None:
        task["status"] = status
    _write_tasks(tasks)
    return task


def _encode_segment(value: dict) -> str:
    encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def _decode_segment(value: str) -> dict:
    padding = "=" * (-len(value) % 4)
    decoded = base64.urlsafe_b64decode(value + padding)
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError("JWT payload must be an object")
    return data


def create_token(user: dict) -> str:
    header = _encode_segment({"alg": "HS256", "typ": "JWT"})
    payload = _encode_segment({"sub": user["id"], "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS})
    message = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('ascii')}"


def _user_from_token(token: str) -> dict | None:
    try:
        header, payload, signature = token.split(".")
        expected = hmac.new(
            JWT_SECRET.encode("utf-8"), f"{header}.{payload}".encode("ascii"), hashlib.sha256
        ).digest()
        provided = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        claims = _decode_segment(payload)
        if not hmac.compare_digest(expected, provided) or claims.get("exp", 0) < time.time():
            return None
        subject = claims.get("sub")
        return get_user_by_id(subject) if isinstance(subject, int) else None
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _unauthorized():
    return jsonify({"error": "authentication required"}), 401


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return _unauthorized()
        user = _user_from_token(token)
        if user is None:
            return _unauthorized()
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def _credentials_from(data: dict) -> tuple[str, str] | None:
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return None
    return username.strip(), password


def _title_from(data: dict) -> str | None:
    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    return title.strip()


@app.route("/auth/register", methods=["POST"])
def register():
    credentials = _credentials_from(request.get_json(silent=True) or {})
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    user = create_user(*credentials)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    credentials = _credentials_from(request.get_json(silent=True) or {})
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    user = get_user_by_username(credentials[0])
    if user is None or not check_password_hash(user["password_hash"], credentials[1]):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user)})


@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.current_user["id"]))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task():
    data = request.get_json(silent=True) or {}
    title = _title_from(data)
    if title is None:
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title, g.current_user["id"])), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.current_user["id"])
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(task_id: int):
    data = request.get_json(silent=True) or {}
    if not any(field in data for field in ("title", "status")):
        return jsonify({"error": "title or status is required"}), 400
    title = None
    if "title" in data:
        title = _title_from(data)
        if title is None:
            return jsonify({"error": "title is required"}), 400
    status = data.get("status")
    if "status" in data and not isinstance(status, str):
        return jsonify({"error": "status must be a string"}), 400
    task = update_task(task_id, g.current_user["id"], title=title, status=status)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run(debug=True)
