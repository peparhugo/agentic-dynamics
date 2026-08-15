import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from threading import RLock

import jwt
from flask import Flask, g, jsonify, request
from jwt import InvalidTokenError
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email


app = Flask(__name__)
logger = logging.getLogger(__name__)
app.config.update(
    DATA_FILE=os.environ.get("TASKS_FILE", "tasks.json"),
    USER_DATA_FILE=os.environ.get("USERS_FILE"),
    JWT_SECRET=os.environ.get("JWT_SECRET", os.urandom(32).hex()),
    JWT_EXPIRATION_SECONDS=3600,
)

_storage_lock = RLock()


def _data_file() -> Path:
    return Path(app.config["DATA_FILE"])


def _users_file() -> Path:
    configured = app.config.get("USER_DATA_FILE")
    if configured:
        return Path(configured)
    task_file = _data_file()
    return task_file.with_name(f"{task_file.stem}.users.json")


def _write_json(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as store:
            json.dump(data, store, indent=2)
            store.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _read_json(path: Path, storage_name: str) -> list[dict]:
    try:
        with path.open(encoding="utf-8") as store:
            data = json.load(store)
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"{storage_name} storage is unreadable") from exc
    if not isinstance(data, list):
        raise RuntimeError(f"{storage_name} storage is invalid")
    return data


def init_storage() -> None:
    """Create stores and migrate tasks written before ownership was added."""
    with _storage_lock:
        task_file = _data_file()
        user_file = _users_file()
        task_file.parent.mkdir(parents=True, exist_ok=True)
        user_file.parent.mkdir(parents=True, exist_ok=True)
        if not task_file.exists():
            _write_json(task_file, [])
        if not user_file.exists():
            _write_json(user_file, [])

        tasks = _read_json(task_file, "task")
        migrated = False
        for task in tasks:
            if isinstance(task, dict) and "owner_id" not in task:
                task["owner_id"] = None
                migrated = True
        if migrated:
            _write_json(task_file, tasks)


def _read_tasks() -> list[dict]:
    init_storage()
    with _storage_lock:
        return _read_json(_data_file(), "task")


def _write_tasks(tasks: list[dict]) -> None:
    _write_json(_data_file(), tasks)


def _read_users() -> list[dict]:
    init_storage()
    with _storage_lock:
        return _read_json(_users_file(), "user")


def create_user(username: str, password: str) -> dict | None:
    with _storage_lock:
        users = _read_users()
        if any(user["username"] == username for user in users):
            return None
        user = {
            "id": max((user["id"] for user in users), default=0) + 1,
            "username": username,
            "password_hash": generate_password_hash(password, method="scrypt"),
        }
        users.append(user)
        _write_json(_users_file(), users)
        return user


def authenticate_user(username: str, password: str) -> dict | None:
    user = next(
        (user for user in _read_users() if user["username"] == username), None
    )
    if user is None or not check_password_hash(user["password_hash"], password):
        return None
    return user


def get_user(user_id: int) -> dict | None:
    return next((user for user in _read_users() if user["id"] == user_id), None)


def _issue_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"]),
    }
    return jwt.encode(payload, app.config["JWT_SECRET"], algorithm="HS256")


def require_auth(view):
    @wraps(view)
    def authenticated_view(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401
        try:
            payload = jwt.decode(
                token, app.config["JWT_SECRET"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify({"error": "invalid token"}), 401

        if not any(user["id"] == user_id for user in _read_users()):
            return jsonify({"error": "invalid token"}), 401
        g.user_id = user_id
        return view(*args, **kwargs)

    return authenticated_view


def create_task(title: str, owner_id: int) -> dict:
    with _storage_lock:
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
    tasks = [task for task in _read_tasks() if task.get("owner_id") == owner_id]
    return sorted(tasks, key=lambda task: task["created_at"], reverse=True)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return next(
        (
            task
            for task in _read_tasks()
            if task["id"] == task_id and task.get("owner_id") == owner_id
        ),
        None,
    )


def update_task(
    task_id: int,
    owner_id: int,
    title: str | None = None,
    status: str | None = None,
) -> dict | None:
    with _storage_lock:
        tasks = _read_tasks()
        task = next(
            (
                task
                for task in tasks
                if task["id"] == task_id and task.get("owner_id") == owner_id
            ),
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


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _credentials() -> tuple[str, str] | None:
    data = _json_body()
    if data is None:
        return None
    username = data.get("username")
    password = data.get("password")
    if (
        not isinstance(username, str)
        or not username.strip()
        or not isinstance(password, str)
        or not password
    ):
        return None
    return username.strip(), password


@app.post("/auth/register")
def register():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    user = create_user(username, password)
    if user is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.post("/auth/login")
def login():
    credentials = _credentials()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    user = authenticate_user(*credentials)
    if user is None:
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": _issue_token(user["id"])})


@app.get("/tasks")
@require_auth
def list_tasks():
    return jsonify(get_tasks(g.user_id))


@app.post("/tasks")
@require_auth
def add_task():
    data = _json_body()
    title = data.get("title") if data is not None else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400
    return jsonify(create_task(title.strip(), g.user_id)), 201


@app.get("/tasks/<int:task_id>")
@require_auth
def show_task(task_id: int):
    task = get_task(task_id, g.user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def edit_task(task_id: int):
    existing_task = get_task(task_id, g.user_id)
    if existing_task is None:
        return jsonify({"error": "task not found"}), 404

    data = _json_body()
    if data is None:
        return jsonify({"error": "JSON object is required"}), 400
    if "title" in data and (
        not isinstance(data["title"], str) or not data["title"].strip()
    ):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400

    title = data["title"].strip() if "title" in data else None
    task = update_task(
        task_id, g.user_id, title=title, status=data.get("status")
    )
    if existing_task["status"] != "completed" and task["status"] == "completed":
        owner = get_user(g.user_id)
        try:
            send_notification_email.delay(owner["username"], task["title"])
        except Exception:
            logger.exception("Could not queue completion notification for task %s", task_id)
    return jsonify(task)


@app.errorhandler(404)
def route_not_found(_error):
    return jsonify({"error": "not found"}), 404


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
