import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import BaseRepository, TaskRepository, UserRepository, init_storage


_default_jwt_secret = secrets.token_bytes(32)


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

        user_repository = current_app.extensions["user_repository"]
        user = user_repository.get_by_id(user_id)
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

    task_repository, user_repository = init_storage(
        app.config["TASKS_FILE"], app.config["USERS_FILE"]
    )
    app.extensions["task_repository"] = task_repository
    app.extensions["user_repository"] = user_repository

    @app.post("/auth/register")
    def register():
        data = _json_body()
        credentials = _valid_credentials(data)
        if credentials is None:
            return jsonify(error="username and password are required"), 400
        username, password = credentials
        email = data.get("email")
        if email is not None and (
            not isinstance(email, str) or not email.strip()
        ):
            return jsonify(error="email must be a non-empty string"), 400

        user = user_repository.create_user(
            username,
            email.strip() if email is not None else username,
            generate_password_hash(password, method="scrypt"),
        )
        if user is None:
            return jsonify(error="username already exists"), 409
        return jsonify(id=user["id"], username=user["username"]), 201

    @app.post("/auth/login")
    def login():
        credentials = _valid_credentials(_json_body())
        if credentials is None:
            return jsonify(error="username and password are required"), 400
        username, password = credentials

        user = user_repository.get_by_username(username)
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

        task = task_repository.create_for_owner(
            title.strip(),
            g.current_user["id"],
            datetime.now(timezone.utc).isoformat(),
        )
        return jsonify(task), 201

    @app.get("/tasks")
    @_authentication_required
    def list_tasks():
        tasks = task_repository.list_for_owner(g.current_user["id"])
        return jsonify(tasks)

    @app.get("/tasks/<int:task_id>")
    @_authentication_required
    def get_task(task_id: int):
        task = task_repository.get_for_owner(task_id, g.current_user["id"])
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

        changes = {
            field: data[field].strip()
            for field in ("title", "status")
            if field in data
        }
        updated = task_repository.update_for_owner(
            task_id, g.current_user["id"], changes
        )
        if updated is None:
            return jsonify(error="task not found"), 404
        task_result, previous_task = updated
        status_changed_to_completed = (
            task_result.get("status") == "completed"
            and previous_task.get("status") != "completed"
        )
        if status_changed_to_completed:
            owner_email = g.current_user.get("email", g.current_user["username"])
            send_notification_email.delay(owner_email, task_result["title"])
        return jsonify(task_result)

    return app


app = create_app()


if __name__ == "__main__":
    app.run()
