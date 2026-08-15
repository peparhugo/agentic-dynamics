"""A small Flask API for managing tasks.

Tasks are persisted in a JSON file.  The explicit flat-file storage
requirement means this service does not use a database.
"""

from datetime import datetime, timedelta, timezone
import base64
import binascii
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
from threading import Lock

from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
DATA_FILE = Path(os.environ.get("TASKS_FILE", "tasks.json"))
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "development-secret-change-me")
JWT_LIFETIME = timedelta(hours=1)
_file_lock = Lock()


def init_storage():
    """Create the flat-file storage and its initial document if needed."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        _write_data({"next_id": 1, "next_user_id": 1, "users": [], "tasks": []})


def _read_data():
    init_storage()
    try:
        with DATA_FILE.open("r", encoding="utf-8") as data_file:
            data = json.load(data_file)
    except (OSError, json.JSONDecodeError):
        data = {"next_id": 1, "tasks": []}
    migrated = False
    if "next_id" not in data:
        data["next_id"] = 1
        migrated = True
    if "next_user_id" not in data:
        data["next_user_id"] = 1
        migrated = True
    if "users" not in data:
        data["users"] = []
        migrated = True
    if "tasks" not in data:
        data["tasks"] = []
        migrated = True
    # Migration for files created before authentication was introduced.
    for task in data["tasks"]:
        if "owner_id" not in task:
            task["owner_id"] = None
            migrated = True
    if migrated:
        _write_data(data)
    return data


def _write_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=DATA_FILE.parent, prefix=f".{DATA_FILE.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(data, temporary_file, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, DATA_FILE)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _task_response(task):
    return jsonify(task)


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _create_token(user):
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({
        "sub": str(user["id"]),
        "username": user["username"],
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int((datetime.now(timezone.utc) + JWT_LIFETIME).timestamp()),
    }, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(app.config["JWT_SECRET_KEY"].encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode(signature)}"


def _current_user():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    try:
        header, payload, signature = authorization[7:].split(".")
        expected = hmac.new(
            app.config["JWT_SECRET_KEY"].encode(), f"{header}.{payload}".encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(_decode(signature), expected):
            return None
        token_header = json.loads(_decode(header))
        claims = json.loads(_decode(payload))
        if token_header.get("alg") != "HS256" or token_header.get("typ") != "JWT":
            return None
        if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        user_id = int(claims["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error, OverflowError):
        return None
    with _file_lock:
        return next((user for user in _read_data()["users"] if user["id"] == user_id), None)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = _current_user()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.user = user
        return view(*args, **kwargs)

    return wrapped


@app.post("/auth/register")
def register():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
        return jsonify({"error": "username and password are required"}), 400
    username = username.strip()
    with _file_lock:
        storage = _read_data()
        if any(user["username"] == username for user in storage["users"]):
            return jsonify({"error": "username already exists"}), 409
        user = {"id": storage["next_user_id"], "username": username, "password_hash": generate_password_hash(password)}
        storage["next_user_id"] += 1
        storage["users"].append(user)
        _write_data(storage)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    with _file_lock:
        user = next((user for user in _read_data()["users"] if user["username"] == username), None)
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": _create_token(user)})


@app.post("/tasks")
@require_auth
def create_task():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("title"), str) or not data["title"].strip():
        return jsonify({"error": "title is required"}), 400

    with _file_lock:
        storage = _read_data()
        task = {
            "id": storage["next_id"],
            "title": data["title"].strip(),
            "status": "pending",
            "created_at": _now(),
            "owner_id": g.user["id"],
        }
        storage["next_id"] += 1
        storage["tasks"].append(task)
        _write_data(storage)
    return _task_response(task), 201


@app.get("/tasks")
@require_auth
def list_tasks():
    with _file_lock:
        tasks = [task for task in _read_data()["tasks"] if task.get("owner_id") == g.user["id"]]
    tasks.sort(key=lambda task: (task.get("created_at", ""), task.get("id", 0)), reverse=True)
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
@require_auth
def get_task(task_id):
    with _file_lock:
        task = next((task for task in _read_data()["tasks"] if task["id"] == task_id and task.get("owner_id") == g.user["id"]), None)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return _task_response(task)


@app.put("/tasks/<int:task_id>")
@require_auth
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required"}), 400

    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify({"error": "title must be a non-empty string"}), 400
    if "status" in data and not isinstance(data["status"], str):
        return jsonify({"error": "status must be a string"}), 400
    if not ("title" in data or "status" in data):
        return jsonify({"error": "title or status is required"}), 400

    with _file_lock:
        storage = _read_data()
        task = next((task for task in storage["tasks"] if task["id"] == task_id and task.get("owner_id") == g.user["id"]), None)
        if task is None:
            return jsonify({"error": "task not found"}), 404
        if "title" in data:
            task["title"] = data["title"].strip()
        if "status" in data:
            task["status"] = data["status"]
        _write_data(storage)
    return _task_response(task)


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "method not allowed"}), 405


init_storage()


if __name__ == "__main__":
    app.run(debug=True)
