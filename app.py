import base64
import binascii
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Any, Callable

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email


class TaskStore:
    """A small, thread-safe JSON file store for tasks."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.initialize()

    def initialize(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write([])
                return

            tasks = self._read()
            if any("owner_id" not in task for task in tasks):
                for task in tasks:
                    task.setdefault("owner_id", None)
                self._write(tasks)

    def _read(self) -> list[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("task storage must contain a JSON array")
        return data

    def _write(self, tasks: list[dict[str, Any]]) -> None:
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(tasks, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, self.path)

    def create(self, title: str, owner_id: int) -> dict[str, Any]:
        with self._lock:
            tasks = self._read()
            task = {
                "id": max((task["id"] for task in tasks), default=0) + 1,
                "title": title,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "owner_id": owner_id,
            }
            tasks.append(task)
            self._write(tasks)
            return task

    def list(self, owner_id: int) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(
                (task for task in self._read() if task.get("owner_id") == owner_id),
                key=lambda task: task["created_at"],
                reverse=True,
            )

    def get(self, task_id: int, owner_id: int) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (
                    task
                    for task in self._read()
                    if task["id"] == task_id and task.get("owner_id") == owner_id
                ),
                None,
            )

    def update(
        self, task_id: int, owner_id: int, changes: dict[str, str]
    ) -> dict[str, Any] | None:
        with self._lock:
            tasks = self._read()
            for task in tasks:
                if task["id"] == task_id and task.get("owner_id") == owner_id:
                    task.update(changes)
                    self._write(tasks)
                    return task
            return None


class UserStore:
    """A thread-safe JSON file store for users."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = RLock()
        self.initialize()

    def initialize(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                self._write([])

    def _read(self) -> list[dict[str, Any]]:
        with self.path.open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError("user storage must contain a JSON array")
        return data

    def _write(self, users: list[dict[str, Any]]) -> None:
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(users, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, self.path)

    def create(
        self, username: str, password: str, email: str | None = None
    ) -> dict[str, Any] | None:
        with self._lock:
            users = self._read()
            if any(user["username"] == username for user in users):
                return None
            user = {
                "id": max((user["id"] for user in users), default=0) + 1,
                "username": username,
                "email": email or username,
                "password_hash": generate_password_hash(password),
            }
            users.append(user)
            self._write(users)
            return user

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (user for user in self._read() if user["username"] == username), None
            )

    def get(self, user_id: int) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (user for user in self._read() if user["id"] == user_id), None
            )


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int, secret: str, lifetime_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=lifetime_seconds)).timestamp()),
    }
    segments = [
        _base64url_encode(json.dumps(header, separators=(",", ":")).encode()),
        _base64url_encode(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments)
    signature = hmac.new(
        secret.encode(), signing_input.encode("ascii"), hashlib.sha256
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def decode_token(token: str, secret: str) -> int | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}"
        expected_signature = hmac.new(
            secret.encode(), signing_input.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(
            _base64url_decode(encoded_signature), expected_signature
        ):
            return None
        header = json.loads(_base64url_decode(encoded_header))
        payload = json.loads(_base64url_decode(encoded_payload))
        if not isinstance(header, dict) or not isinstance(payload, dict):
            return None
        if header.get("alg") != "HS256":
            return None
        subject = payload.get("sub")
        expires_at = payload.get("exp")
        if (
            not isinstance(subject, str)
            or not subject.isdigit()
            or not isinstance(expires_at, (int, float))
            or isinstance(expires_at, bool)
            or datetime.now(timezone.utc).timestamp() >= expires_at
        ):
            return None
        return int(subject)
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        binascii.Error,
        json.JSONDecodeError,
    ):
        return None


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        TASKS_FILE=os.environ.get(
            "TASKS_FILE", str(Path(app.instance_path) / "tasks.json")
        ),
        USERS_FILE=os.environ.get(
            "USERS_FILE", str(Path(app.instance_path) / "users.json")
        ),
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-secret"),
        JWT_LIFETIME_SECONDS=3600,
    )
    if config:
        app.config.update(config)
        if "TASKS_FILE" in config and "USERS_FILE" not in config:
            app.config["USERS_FILE"] = str(
                Path(config["TASKS_FILE"]).with_name("users.json")
            )

    task_store = TaskStore(app.config["TASKS_FILE"])
    user_store = UserStore(app.config["USERS_FILE"])
    app.extensions["task_store"] = task_store
    app.extensions["user_store"] = user_store

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any):
            authorization = request.headers.get("Authorization", "")
            scheme, separator, token = authorization.partition(" ")
            if separator != " " or scheme.lower() != "bearer" or not token:
                return jsonify(error="authentication required"), 401
            user_id = decode_token(token, app.config["JWT_SECRET_KEY"])
            if user_id is None:
                return jsonify(error="invalid or expired token"), 401
            g.user_id = user_id
            return view(*args, **kwargs)

        return wrapped

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True)
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        email = data.get("email") if isinstance(data, dict) else None
        if not isinstance(username, str) or not username.strip():
            return jsonify(error="username is required"), 400
        if not isinstance(password, str) or not password:
            return jsonify(error="password is required"), 400
        if email is not None and (not isinstance(email, str) or not email.strip()):
            return jsonify(error="email must be a non-empty string"), 400

        user = user_store.create(
            username.strip(), password, email.strip() if email is not None else None
        )
        if user is None:
            return jsonify(error="username already exists"), 409
        return jsonify(id=user["id"], username=user["username"]), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True)
        username = data.get("username") if isinstance(data, dict) else None
        password = data.get("password") if isinstance(data, dict) else None
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify(error="username and password are required"), 400

        user = user_store.get_by_username(username.strip())
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify(error="invalid username or password"), 401
        token = create_token(
            user["id"],
            app.config["JWT_SECRET_KEY"],
            app.config["JWT_LIFETIME_SECONDS"],
        )
        return jsonify(token=token)

    @app.post("/tasks")
    @require_auth
    def create_task():
        data = request.get_json(silent=True)
        title = data.get("title") if isinstance(data, dict) else None
        if not isinstance(title, str) or not title.strip():
            return jsonify(error="title is required"), 400

        return jsonify(task_store.create(title.strip(), g.user_id)), 201

    @app.get("/tasks")
    @require_auth
    def list_tasks():
        return jsonify(task_store.list(g.user_id))

    @app.get("/tasks/<int:task_id>")
    @require_auth
    def get_task(task_id: int):
        task = task_store.get(task_id, g.user_id)
        if task is None:
            return jsonify(error="task not found"), 404
        return jsonify(task)

    @app.put("/tasks/<int:task_id>")
    @require_auth
    def update_task(task_id: int):
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="JSON body is required"), 400

        changes = {}
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify(error="title must be a non-empty string"), 400
            changes["title"] = data["title"].strip()
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify(error="status must be a non-empty string"), 400
            changes["status"] = data["status"].strip()
        if not changes:
            return jsonify(error="title or status is required"), 400

        existing_task = task_store.get(task_id, g.user_id)
        task = task_store.update(task_id, g.user_id, changes)
        if task is None:
            return jsonify(error="task not found"), 404
        if (
            existing_task is not None
            and existing_task["status"] != "completed"
            and task["status"] == "completed"
        ):
            owner = user_store.get(g.user_id)
            if owner is not None:
                try:
                    send_notification_email.delay(
                        owner.get("email", owner["username"]), task["title"]
                    )
                except Exception:
                    app.logger.exception(
                        "Could not enqueue completion notification for task %s", task_id
                    )
        return jsonify(task)

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
