import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notification_tasks import send_notification_email
from repositories import (
    BaseRepository,
    DuplicateUsernameError,
    TaskRepository,
    UserRepository,
)


DATABASE = os.environ.get("DATABASE", "tasks.db")


def get_db():
    return BaseRepository.connect(DATABASE)


def init_db() -> None:
    UserRepository(DATABASE).initialize_schema()
    TaskRepository(DATABASE).initialize_schema()


def task_to_dict(task) -> dict:
    return {
        "id": task["id"],
        "title": task["title"],
        "status": task["status"],
        "created_at": task["created_at"],
    }


def json_body() -> dict | None:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def create_app(config: dict | None = None) -> Flask:
    global DATABASE

    application = Flask(__name__)
    application.config.from_mapping(
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "development-secret-change-me"),
        JWT_EXPIRATION_SECONDS=3600,
    )
    if config:
        application.config.update(config)
        if config.get("DATABASE"):
            DATABASE = config["DATABASE"]

    user_repository = UserRepository(DATABASE)
    task_repository = TaskRepository(DATABASE)

    def token_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            authorization = request.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() != "bearer" or not token:
                return jsonify({"error": "authentication required"}), 401

            try:
                payload = jwt.decode(
                    token,
                    application.config["JWT_SECRET_KEY"],
                    algorithms=["HS256"],
                )
                user_id = int(payload["sub"])
            except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
                return jsonify({"error": "invalid token"}), 401

            user = user_repository.get_by_id(user_id)
            if user is None:
                return jsonify({"error": "invalid token"}), 401

            g.user_id = user["id"]
            g.username = user["username"]
            return view(*args, **kwargs)

        return wrapped

    @application.post("/auth/register")
    def register():
        data = json_body()
        username = data.get("username") if data else None
        password = data.get("password") if data else None
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400

        try:
            user = user_repository.create_user(
                username.strip(), generate_password_hash(password)
            )
        except DuplicateUsernameError:
            return jsonify({"error": "username already exists"}), 409

        return jsonify({"id": user["id"], "username": username.strip()}), 201

    @application.post("/auth/login")
    def login():
        data = json_body()
        username = data.get("username") if data else None
        password = data.get("password") if data else None
        if not isinstance(username, str) or not isinstance(password, str):
            return jsonify({"error": "username and password are required"}), 400

        user = user_repository.get_by_username(username.strip())
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid credentials"}), 401

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": str(user["id"]),
                "iat": now,
                "exp": now
                + timedelta(seconds=application.config["JWT_EXPIRATION_SECONDS"]),
            },
            application.config["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        return jsonify({"token": token})

    @application.post("/tasks")
    @token_required
    def create_task():
        data = json_body()
        title = data.get("title") if data else None
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400

        title = title.strip()
        created_at = datetime.now(timezone.utc).isoformat()
        task = task_repository.create_task(title, created_at, g.user_id)

        return jsonify(task_to_dict(task)), 201

    @application.get("/tasks")
    @token_required
    def list_tasks():
        tasks = task_repository.list_for_owner(g.user_id)
        return jsonify([task_to_dict(task) for task in tasks])

    @application.get("/tasks/<int:task_id>")
    @token_required
    def get_task(task_id: int):
        task = task_repository.get_for_owner(task_id, g.user_id)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task_to_dict(task))

    @application.put("/tasks/<int:task_id>")
    @token_required
    def update_task(task_id: int):
        data = json_body()
        if data is None:
            return jsonify({"error": "JSON object is required"}), 400

        updates = {}
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            updates["title"] = data["title"].strip()
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            updates["status"] = data["status"].strip()
        if not updates:
            return jsonify({"error": "title or status is required"}), 400

        existing = task_repository.get_for_owner(task_id, g.user_id)
        if existing is None:
            return jsonify({"error": "task not found"}), 404

        task = task_repository.update_for_owner(task_id, g.user_id, updates)

        if existing["status"] != "completed" and task["status"] == "completed":
            send_notification_email.delay(g.username, task["title"])

        return jsonify(task_to_dict(task))

    init_db()
    return application


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
