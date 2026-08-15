import json
import os
import secrets
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


_storage_lock = threading.RLock()
_default_jwt_secret = secrets.token_bytes(32)


def _tasks_path() -> Path:
    return Path(current_app.config["TASKS_FILE"])


def _users_path() -> Path:
    return Path(current_app.config["USERS_FILE"])


def _initialize_json_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")


def _read_json_list(path: Path, description: str) -> list[dict]:
    _initialize_json_file(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"{description} storage could not be read") from exc
    if not isinstance(data, list):
        raise RuntimeError(f"{description} storage has an invalid format")
    return data


def _write_json_list(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temporary_file:
            json.dump(records, temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def init_storage(
    tasks_path: str | os.PathLike[str], users_path: str | os.PathLike[str]
) -> None:
    """Initialize storage and add ownership metadata to legacy tasks."""
    tasks_storage = Path(tasks_path)
    users_storage = Path(users_path)
    with _storage_lock:
        _initialize_json_file(tasks_storage)
        _initialize_json_file(users_storage)
        tasks = _read_json_list(tasks_storage, "Task")
        migrated = False
        for task in tasks:
            if "owner_id" not in task:
                task["owner_id"] = None
                migrated = True
        if migrated:
            _write_json_list(tasks_storage, tasks)


def _read_tasks() -> list[dict]:
    return _read_json_list(_tasks_path(), "Task")


def _write_tasks(tasks: list[dict]) -> None:
    _write_json_list(_tasks_path(), tasks)


def _read_users() -> list[dict]:
    return _read_json_list(_users_path(), "User")


def _write_users(users: list[dict]) -> None:
    _write_json_list(_users_path(), users)


def _json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def _valid_credentials(data: dict | None) -> tuple[str, str] | None:
    if data is None:
        return None
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return None
    if not isinstance(password, str) or not password:
        return None
    return username.strip(), password


def _authentication_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token:
            return jsonify(error="authentication required"), 401
        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=["HS256"],
            )
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return jsonify(error="invalid token"), 401

        with _storage_lock:
            users = _read_users()
        user = next((user for user in users if user["id"] == user_id), None)
        if user is None:
            return jsonify(error="invalid token"), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        TASKS_FILE=os.environ.get(
            "TASKS_FILE", str(Path(app.instance_path) / "tasks.json")
        ),
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", _default_jwt_secret),
        JWT_EXPIRATION_SECONDS=3600,
    )
    if config:
        app.config.update(config)
    if not app.config.get("USERS_FILE"):
        app.config["USERS_FILE"] = str(
            Path(app.config["TASKS_FILE"]).with_name("users.json")
        )

    init_storage(app.config["TASKS_FILE"], app.config["USERS_FILE"])

    @app.post("/auth/register")
    def register():
        credentials = _valid_credentials(_json_body())
        if credentials is None:
            return jsonify(error="username and password are required"), 400
        username, password = credentials

        with _storage_lock:
            users = _read_users()
            if any(user["username"] == username for user in users):
                return jsonify(error="username already exists"), 409
            user = {
                "id": max((user["id"] for user in users), default=0) + 1,
                "username": username,
                "password_hash": generate_password_hash(password, method="scrypt"),
            }
            users.append(user)
            _write_users(users)
        return jsonify(id=user["id"], username=user["username"]), 201

    @app.post("/auth/login")
    def login():
        credentials = _valid_credentials(_json_body())
        if credentials is None:
            return jsonify(error="username and password are required"), 400
        username, password = credentials

        with _storage_lock:
            users = _read_users()
        user = next((user for user in users if user["username"] == username), None)
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify(error="invalid username or password"), 401

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user["id"]),
                "iat": now,
                "exp": now
                + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"]),
            },
            app.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify(token=token)

    @app.post("/tasks")
    @_authentication_required
    def create_task():
        data = _json_body()
        title = data.get("title") if data is not None else None
        if not isinstance(title, str) or not title.strip():
            return jsonify(error="title is required"), 400

        with _storage_lock:
            tasks = _read_tasks()
            task = {
                "id": max((task["id"] for task in tasks), default=0) + 1,
                "title": title.strip(),
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "owner_id": g.current_user["id"],
            }
            tasks.append(task)
            _write_tasks(tasks)
        return jsonify(task), 201

    @app.get("/tasks")
    @_authentication_required
    def list_tasks():
        with _storage_lock:
            tasks = [
                task
                for task in _read_tasks()
                if task.get("owner_id") == g.current_user["id"]
            ]
        tasks.sort(key=lambda task: task["created_at"], reverse=True)
        return jsonify(tasks)

    @app.get("/tasks/<int:task_id>")
    @_authentication_required
    def get_task(task_id: int):
        with _storage_lock:
            tasks = _read_tasks()
        task = next(
            (
                task
                for task in tasks
                if task["id"] == task_id
                and task.get("owner_id") == g.current_user["id"]
            ),
            None,
        )
        if task is None:
            return jsonify(error="task not found"), 404
        return jsonify(task)

    @app.put("/tasks/<int:task_id>")
    @_authentication_required
    def update_task(task_id: int):
        data = _json_body()
        if data is None:
            return jsonify(error="JSON object is required"), 400

        if "title" in data and (
            not isinstance(data["title"], str) or not data["title"].strip()
        ):
            return jsonify(error="title must be a non-empty string"), 400
        if "status" in data and (
            not isinstance(data["status"], str) or not data["status"].strip()
        ):
            return jsonify(error="status must be a non-empty string"), 400
        if not any(field in data for field in ("title", "status")):
            return jsonify(error="title or status is required"), 400

        with _storage_lock:
            tasks = _read_tasks()
            task = next(
                (
                    task
                    for task in tasks
                    if task["id"] == task_id
                    and task.get("owner_id") == g.current_user["id"]
                ),
                None,
            )
            if task is None:
                return jsonify(error="task not found"), 404
            if "title" in data:
                task["title"] = data["title"].strip()
            if "status" in data:
                task["status"] = data["status"].strip()
            _write_tasks(tasks)
        return jsonify(task)

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
