"""Flask API for managing tasks stored in SQLite."""

from datetime import datetime, timedelta, timezone
from functools import wraps
import os

from flask import Flask, jsonify, request
import jwt
from werkzeug.security import check_password_hash, generate_password_hash
from tasks import send_notification_email
from repositories import TaskRepository, UserRepository

app = Flask(__name__)

DATABASE = os.environ.get("DATABASE", "todos.db")
JWT_SECRET = os.environ.get("JWT_SECRET", "development-secret-change-me")
JWT_ALGORITHM = "HS256"
JWT_LIFETIME = timedelta(hours=1)


def init_db():
    UserRepository(DATABASE).initialize_database(
        generate_password_hash(os.urandom(16).hex())
    )


# ── Models ────────────────────────────────────────────────────

def create_task(title: str, owner_id: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    task_id = TaskRepository(DATABASE).create_task(title, owner_id, now)
    return {"id": task_id, "title": title, "status": "pending", "created_at": now}


def get_tasks(owner_id: int):
    return TaskRepository(DATABASE).get_tasks(owner_id)


def get_task(task_id: int, owner_id: int) -> dict | None:
    return TaskRepository(DATABASE).get_task(task_id, owner_id)


def get_user_email(user_id: int) -> str | None:
    return UserRepository(DATABASE).get_email(user_id)


def update_task(task_id: int, owner_id: int, title: str | None = None, status: str | None = None) -> dict | None:
    values = {key: value for key, value in (("title", title), ("status", status)) if value is not None}
    return TaskRepository(DATABASE).update_task(task_id, owner_id, values)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "authentication required"}), 401
        token = header[7:].strip()
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            if not isinstance(user_id, str) or not user_id.isdigit():
                raise jwt.InvalidTokenError
            user_id = int(user_id)
        except jwt.InvalidTokenError:
            return jsonify({"error": "invalid or expired token"}), 401
        return view(user_id, *args, **kwargs)

    return wrapped


# ── Routes ─────────────────────────────────────────────────────

@app.route("/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    username, password = data.get("username"), data.get("password")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    if email is not None and (not isinstance(email, str) or not email.strip()):
        return jsonify({"error": "email must be a non-empty string"}), 400
    username = username.strip()
    email = email.strip() if isinstance(email, str) else None
    user_id = UserRepository(DATABASE).create_user(
        username, generate_password_hash(password), email
    )
    if user_id is None:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    username, password = data.get("username"), data.get("password")
    user = UserRepository(DATABASE).get_by_username(username)
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    token = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) + JWT_LIFETIME},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return jsonify({"token": token})

@app.route("/tasks", methods=["GET"])
@require_auth
def list_tasks(user_id):
    return jsonify(get_tasks(user_id))


@app.route("/tasks", methods=["POST"])
@require_auth
def add_task(user_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    title = data.get("title")
    if not isinstance(title, str):
        title = ""
    title = title.strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    task = create_task(title, user_id)
    return jsonify(task), 201


@app.route("/tasks/<int:task_id>", methods=["GET"])
@require_auth
def show_task(user_id, task_id: int):
    task = get_task(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task)


@app.route("/tasks/<int:task_id>", methods=["PUT"])
@require_auth
def edit_task(user_id, task_id: int):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body must be an object"}), 400
    previous_task = get_task(task_id, user_id)
    if previous_task is None:
        return jsonify({"error": "task not found"}), 404
    if "title" not in data and "status" not in data:
        return jsonify({"error": "title or status is required"}), 400
    if "title" in data and not isinstance(data["title"], str):
        return jsonify({"error": "title must be a string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    task = update_task(
        task_id, user_id,
        title=data.get("title"),
        status=data.get("status"),
    )
    if task is None:
        return jsonify({"error": "task not found"}), 404
    if previous_task["status"] != "completed" and task["status"] == "completed":
        user_email = get_user_email(user_id)
        if user_email:
            send_notification_email.delay(user_email, task["title"])
    return jsonify(task)


# Ensure the database is usable when the application is imported by a WSGI
# server or a test runner, not only when this module is executed as a script.
init_db()


if __name__ == "__main__":
    app.run(debug=True)
