import base64
import binascii
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from flask import Flask, g, jsonify, request
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash

from notification_tasks import send_notification_email
from repositories import TaskRepository, UserRepository


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
        RATELIMIT_DEFAULT="100 per minute",
        RATELIMIT_STORAGE_URI=os.environ.get(
            "RATELIMIT_STORAGE_URI", "redis://localhost:6379"
        ),
        RATELIMIT_HEADERS_ENABLED=True,
        RATELIMIT_HEADER_RETRY_AFTER_VALUE="delta-seconds",
    )
    if config:
        app.config.update(config)
        if "TASKS_FILE" in config and "USERS_FILE" not in config:
            app.config["USERS_FILE"] = str(
                Path(config["TASKS_FILE"]).with_name("users.json")
            )
    if app.config["TESTING"] and not (config or {}).get("RATELIMIT_STORAGE_URI"):
        app.config["RATELIMIT_STORAGE_URI"] = "memory://"

    task_repository = TaskRepository(app.config["TASKS_FILE"])
    user_repository = UserRepository(app.config["USERS_FILE"])
    app.extensions["task_repository"] = task_repository
    app.extensions["user_repository"] = user_repository

    def rate_limit_key() -> str:
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if separator == " " and scheme.lower() == "bearer" and token:
            user_id = decode_token(token, app.config["JWT_SECRET_KEY"])
            if user_id is not None:
                return f"user:{user_id}"
        return f"address:{get_remote_address()}"

    limiter = Limiter(key_func=rate_limit_key, app=app)

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(error: RateLimitExceeded):
        return jsonify(error="rate limit exceeded"), 429

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

        user = user_repository.create(
            username=username.strip(),
            password=password,
            email=email.strip() if email is not None else None,
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

        user = user_repository.get_by_username(username.strip())
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

        return jsonify(
            task_repository.create(title=title.strip(), owner_id=g.user_id)
        ), 201

    @app.get("/tasks")
    @require_auth
    def list_tasks():
        cursor_value = request.args.get("cursor")
        limit_value = request.args.get("limit", "20")
        try:
            cursor = int(cursor_value) if cursor_value is not None else None
            limit = int(limit_value)
        except ValueError:
            return jsonify(error="cursor and limit must be integers"), 400
        if cursor is not None and cursor < 1:
            return jsonify(error="cursor must be a positive integer"), 400
        if limit < 1 or limit > 100:
            return jsonify(error="limit must be between 1 and 100"), 400

        tasks, next_cursor, total = task_repository.paginate(
            g.user_id, cursor, limit
        )
        return jsonify(data=tasks, next_cursor=next_cursor, total=total)

    @app.get("/tasks/<int:task_id>")
    @require_auth
    def get_task(task_id: int):
        task = task_repository.get(task_id, g.user_id)
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

        existing_task = task_repository.get(task_id, g.user_id)
        task = task_repository.update(task_id, g.user_id, changes)
        if task is None:
            return jsonify(error="task not found"), 404
        if (
            existing_task is not None
            and existing_task["status"] != "completed"
            and task["status"] == "completed"
        ):
            owner = user_repository.get(g.user_id)
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
