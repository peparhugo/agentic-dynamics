import os
import sqlite3
import base64
import binascii
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from celery_config import celery_app
from notifications import send_notification_email
from repositories import DuplicateUserError, TaskRepository, UserRepository


app = Flask(__name__)
DATABASE = os.environ.get("DATABASE", "tasks.db")
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "development-only-change-me"
)
app.config["JWT_EXPIRATION_SECONDS"] = 3600


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def get_user_repository():
    return UserRepository(get_db)


def get_task_repository():
    return TaskRepository(get_db)


def init_db():
    get_user_repository().initialize()
    get_task_repository().initialize()


def _base64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    now = datetime.now(timezone.utc)
    header = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload = _base64url_encode(
        json.dumps(
            {
                "sub": str(user_id),
                "iat": int(now.timestamp()),
                "exp": int(
                    (now + timedelta(seconds=app.config["JWT_EXPIRATION_SECONDS"]))
                    .timestamp()
                ),
            },
            separators=(",", ":"),
        ).encode()
    )
    message = f"{header}.{payload}"
    signature = hmac.new(
        app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
    ).digest()
    return f"{message}.{_base64url_encode(signature)}"


def decode_token(token):
    try:
        header_part, payload_part, signature_part = token.split(".")
        header = json.loads(_base64url_decode(header_part))
        if header != {"alg": "HS256", "typ": "JWT"}:
            return None
        message = f"{header_part}.{payload_part}"
        expected_signature = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(
            _base64url_decode(signature_part), expected_signature
        ):
            return None
        payload = json.loads(_base64url_decode(payload_part))
        if payload.get("exp", 0) <= datetime.now(timezone.utc).timestamp():
            return None
        return int(payload["sub"])
    except (
        ValueError,
        TypeError,
        KeyError,
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            return jsonify({"error": "authentication required"}), 401

        user_id = decode_token(token)
        if user_id is None:
            return jsonify({"error": "invalid or expired token"}), 401
        user = get_user_repository().find_identity(user_id)
        if user is None:
            return jsonify({"error": "invalid or expired token"}), 401
        g.current_user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def credentials_from_request():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return None
    if not isinstance(password, str) or not password:
        return None
    return username.strip(), password


@app.post("/auth/register")
def register():
    credentials = credentials_from_request()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    data = request.get_json()
    email = data.get("email", username)
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "email must be a non-empty string"}), 400
    email = email.strip()

    try:
        user_id = get_user_repository().create_user(
            username, email, generate_password_hash(password)
        )
    except DuplicateUserError:
        return jsonify({"error": "username already exists"}), 409
    return jsonify({"id": user_id, "username": username}), 201


@app.post("/auth/login")
def login():
    credentials = credentials_from_request()
    if credentials is None:
        return jsonify({"error": "username and password are required"}), 400
    username, password = credentials
    user = get_user_repository().find_by_username(username)
    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid username or password"}), 401
    return jsonify({"token": create_token(user["id"])})


def task_response(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


@app.post("/tasks")
@login_required
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    title = title.strip()
    created_at = datetime.now(timezone.utc).isoformat()
    task_id = get_task_repository().create_task(
        title, "pending", created_at, g.current_user_id
    )

    return jsonify(
        {
            "id": task_id,
            "title": title,
            "status": "pending",
            "created_at": created_at,
        }
    ), 201


@app.get("/tasks")
@login_required
def list_tasks():
    rows = get_task_repository().list_for_owner(g.current_user_id)
    return jsonify([task_response(row) for row in rows])


@app.get("/tasks/<int:task_id>")
@login_required
def get_task(task_id):
    row = get_task_repository().get_for_owner(task_id, g.current_user_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task_response(row))


@app.put("/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON body is required"}), 400

    updates = {}
    if "title" in data:
        if not isinstance(data["title"], str) or not data["title"].strip():
            return jsonify({"error": "title must be a non-empty string"}), 400
        updates["title"] = data["title"].strip()
    if "status" in data:
        if not isinstance(data["status"], str) or not data["status"].strip():
            return jsonify({"error": "status must be a non-empty string"}), 400
        updates["status"] = data["status"].strip()

    exists, row = get_task_repository().update_for_owner(
        task_id, g.current_user_id, updates
    )
    if exists is None:
        return jsonify({"error": "task not found"}), 404

    status_changed_to_completed = (
        "status" in data
        and data["status"].strip() == "completed"
        and exists["status"] != "completed"
    )
    if status_changed_to_completed:
        if app.config["TESTING"]:
            celery_app.conf.task_always_eager = True
        send_notification_email.delay(exists["email"] or exists["username"], row["title"])

    return jsonify(task_response(row))


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({"error": error.description}), error.code


init_db()


if __name__ == "__main__":
    app.run(debug=True)
