"""
Flask API for task management.

Storage is flat-file JSON (see storage.py) — no database is used, per the
project's storage constraint. Tasks are scoped to the authenticated user via
JWT bearer tokens (see auth.py).
"""

import os
import secrets

from flask import Flask, jsonify, request

from auth import create_token, hash_password, require_auth, verify_password
from celery_tasks import send_notification_email
from storage import TaskStore, UserStore

DEFAULT_STORAGE_PATH = os.environ.get("TASKS_STORAGE_PATH", "tasks.json")
DEFAULT_USERS_STORAGE_PATH = os.environ.get("USERS_STORAGE_PATH", "users.json")


def create_app(storage_path: str = DEFAULT_STORAGE_PATH,
                users_storage_path: str = DEFAULT_USERS_STORAGE_PATH) -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
    app.store = TaskStore(storage_path)
    app.user_store = UserStore(users_storage_path)
    auth_required = require_auth(app)

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "not found"}), 404

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        email = data.get("email")
        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400
        if email is not None and (not isinstance(email, str) or "@" not in email):
            return jsonify({"error": "email must be a valid email address"}), 400
        username = username.strip()
        if app.user_store.get_by_username(username) is not None:
            return jsonify({"error": "username already taken"}), 409
        email = email.strip() if email else f"{username}@example.com"
        user = app.user_store.create(username, hash_password(password), email)
        return jsonify({"id": user["id"], "username": user["username"], "email": user["email"]}), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return jsonify({"error": "username and password are required"}), 400
        user = app.user_store.get_by_username(username.strip())
        if user is None or not verify_password(password, user["password_hash"]):
            return jsonify({"error": "invalid username or password"}), 401
        token = create_token(user, app.config["SECRET_KEY"])
        return jsonify({"token": token}), 200

    @app.post("/tasks")
    @auth_required
    def create_task(user):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = app.store.create(title.strip(), owner_id=user["id"])
        return jsonify(task), 201

    @app.get("/tasks")
    @auth_required
    def list_tasks(user):
        return jsonify(app.store.list_all(owner_id=user["id"])), 200

    @app.get("/tasks/<int:task_id>")
    @auth_required
    def get_task(user, task_id):
        task = app.store.get(task_id, owner_id=user["id"])
        if task is None:
            return jsonify({"error": "task not found"}), 404
        return jsonify(task), 200

    @app.put("/tasks/<int:task_id>")
    @auth_required
    def update_task(user, task_id):
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        status = data.get("status")

        if "title" not in data and "status" not in data:
            return jsonify({"error": "title or status is required"}), 400
        if title is not None and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400
        if status is not None and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400

        previous_task = app.store.get(task_id, owner_id=user["id"])
        task = app.store.update(
            task_id,
            owner_id=user["id"],
            title=title.strip() if title is not None else None,
            status=status.strip() if status is not None else None,
        )
        if task is None:
            return jsonify({"error": "task not found"}), 404

        newly_completed = (
            status is not None
            and task["status"] == "completed"
            and (previous_task is None or previous_task["status"] != "completed")
        )
        if newly_completed:
            try:
                send_notification_email.delay(user["email"], task["title"])
            except Exception:
                app.logger.exception(
                    "failed to enqueue completion notification for task %s", task_id
                )

        return jsonify(task), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
