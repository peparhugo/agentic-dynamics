"""Flask API for task management.

Storage is flat-file (JSON), not a database — see storage.py.

Endpoints under /tasks require a valid JWT (see /auth/register and
/auth/login). Each user only sees and manages their own tasks.
"""

import os
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import storage
from tasks import send_notification_email

JWT_ALGORITHM = "HS256"
JWT_EXP_HOURS = 24


def create_app():
    app = Flask(__name__)
    storage.init_storage()

    app.config["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET_KEY", "dev-secret-key-change-in-production-32bytes-min"
    )

    def generate_token(user):
        payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS),
        }
        return jwt.encode(payload, app.config["JWT_SECRET_KEY"], algorithm=JWT_ALGORITHM)

    def require_auth(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Missing or invalid Authorization header"}), 401

            token = auth_header[len("Bearer "):].strip()
            if not token:
                return jsonify({"error": "Missing or invalid Authorization header"}), 401

            try:
                payload = jwt.decode(
                    token, app.config["JWT_SECRET_KEY"], algorithms=[JWT_ALGORITHM]
                )
            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            g.user_id = int(payload["sub"])
            g.username = payload.get("username")
            return f(*args, **kwargs)

        return wrapper

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.route("/auth/register", methods=["POST"])
    def register():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400

        password_hash = generate_password_hash(password)
        user = storage.create_user(username.strip(), password_hash)
        if user is None:
            return jsonify({"error": "username already exists"}), 409

        return jsonify({"id": user["id"], "username": user["username"]}), 201

    @app.route("/auth/login", methods=["POST"])
    def login():
        data = request.get_json(silent=True) or {}
        username = data.get("username")
        password = data.get("password")

        if not isinstance(username, str) or not username.strip():
            return jsonify({"error": "username is required"}), 400
        if not isinstance(password, str) or not password:
            return jsonify({"error": "password is required"}), 400

        user = storage.get_user_by_username(username.strip())
        if user is None or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "invalid username or password"}), 401

        token = generate_token(user)
        return jsonify({"token": token}), 200

    @app.route("/tasks", methods=["POST"])
    @require_auth
    def create_task():
        data = request.get_json(silent=True) or {}
        title = data.get("title")
        if not isinstance(title, str) or not title.strip():
            return jsonify({"error": "title is required"}), 400
        task = storage.create_task(title.strip(), g.user_id)
        return jsonify(task), 201

    @app.route("/tasks", methods=["GET"])
    @require_auth
    def list_tasks():
        return jsonify(storage.list_tasks(g.user_id)), 200

    @app.route("/tasks/<int:task_id>", methods=["GET"])
    @require_auth
    def get_task(task_id):
        task = storage.get_task(task_id)
        if task is None or task.get("owner_id") != g.user_id:
            return jsonify({"error": "Task not found"}), 404
        return jsonify(task), 200

    @app.route("/tasks/<int:task_id>", methods=["PUT"])
    @require_auth
    def update_task(task_id):
        existing = storage.get_task(task_id)
        if existing is None or existing.get("owner_id") != g.user_id:
            return jsonify({"error": "Task not found"}), 404

        data = request.get_json(silent=True) or {}
        has_title = "title" in data
        has_status = "status" in data
        if not has_title and not has_status:
            return jsonify({"error": "title or status is required"}), 400

        title = data.get("title")
        if has_title and (not isinstance(title, str) or not title.strip()):
            return jsonify({"error": "title must be a non-empty string"}), 400

        status = data.get("status")
        if has_status and (not isinstance(status, str) or not status.strip()):
            return jsonify({"error": "status must be a non-empty string"}), 400

        task = storage.update_task(
            task_id,
            title=title.strip() if has_title else None,
            status=status.strip() if has_status else None,
        )

        newly_completed = (
            has_status
            and status.strip() == "completed"
            and existing.get("status") != "completed"
        )
        if newly_completed:
            owner = storage.get_user_by_id(task["owner_id"])
            if owner is not None:
                owner_email = owner.get("email") or f"{owner['username']}@example.com"
                try:
                    send_notification_email.delay(owner_email, task["title"])
                except Exception:
                    app.logger.exception("Failed to enqueue completion notification email")

        return jsonify(task), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
