"""A small Flask task-management API backed by a JSON flat file."""

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from notifications import send_notification_email


app = Flask(__name__)
app.config["TASKS_FILE"] = os.environ.get("TASKS_FILE", "tasks.json")
app.config["JWT_SECRET"] = os.environ.get("JWT_SECRET", "development-secret-change-me")
app.config["JWT_EXPIRATION_MINUTES"] = 60

_storage_lock = Lock()


def _empty_store():
    return {"next_id": 1, "next_user_id": 1, "tasks": [], "users": []}


def init_db():
    """Initialize the flat-file schema and migrate pre-auth task records."""
    path = Path(app.config["TASKS_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_store(_empty_store())
    else:
        store = _read_store()
        store["next_user_id"] = max(
            store["next_user_id"],
            max((user.get("id", 0) for user in store["users"]), default=0) + 1,
        )
        _write_store(store)


def _read_store():
    path = Path(app.config["TASKS_FILE"])
    try:
        with path.open(encoding="utf-8") as file:
            store = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        store = _empty_store()
    store.setdefault("next_id", 1)
    store.setdefault("next_user_id", 1)
    store.setdefault("tasks", [])
    store.setdefault("users", [])
    # The owner_id field is the flat-file migration for stores created before auth.
    for task in store["tasks"]:
        task.setdefault("owner_id", None)
    return store


def _write_store(store):
    path = Path(app.config["TASKS_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace the file atomically so a request cannot observe a partial JSON file.
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as file:
        json.dump(store, file)
        file.write("\n")
        temporary_path = Path(file.name)
    temporary_path.replace(path)


def _find_task(store, task_id):
    return next((task for task in store["tasks"] if task["id"] == task_id), None)


def _not_found():
    return jsonify({"error": "task not found"}), 404


def _encode_part(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_part(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _make_token(user):
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(json.dumps({
        "sub": user["id"],
        "username": user["username"],
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=app.config["JWT_EXPIRATION_MINUTES"])).timestamp()),
    }, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(app.config["JWT_SECRET"].encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{_encode_part(signature)}"


def _current_user_from_token():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    parts = authorization[7:].split(".")
    if len(parts) != 3:
        return None
    header_part, payload_part, signature_part = parts
    message = f"{header_part}.{payload_part}".encode("ascii")
    expected = hmac.new(app.config["JWT_SECRET"].encode(), message, hashlib.sha256).digest()
    try:
        if not hmac.compare_digest(expected, _decode_part(signature_part)):
            return None
        header = json.loads(_decode_part(header_part))
        payload = json.loads(_decode_part(payload_part))
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if header.get("alg") != "HS256" or header.get("typ") != "JWT":
        return None
    if not isinstance(payload.get("exp"), (int, float)) or payload["exp"] < datetime.now(timezone.utc).timestamp():
        return None
    with _storage_lock:
        return next((user for user in _read_store()["users"] if user["id"] == payload.get("sub")), None)


def jwt_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = _current_user_from_token()
        if user is None:
            return jsonify({"error": "authentication required"}), 401
        g.current_user = user
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
    with _storage_lock:
        store = _read_store()
        if any(user["username"] == username for user in store["users"]):
            return jsonify({"error": "username already exists"}), 409
        user = {
            "id": store["next_user_id"],
            "username": username,
            "password_hash": generate_password_hash(password),
        }
        if isinstance(data.get("email"), str) and data["email"].strip():
            user["email"] = data["email"].strip()
        store["next_user_id"] += 1
        store["users"].append(user)
        _write_store(store)
    return jsonify({"id": user["id"], "username": user["username"]}), 201


@app.post("/auth/login")
def login():
    data = request.get_json(silent=True)
    username = data.get("username") if isinstance(data, dict) else None
    password = data.get("password") if isinstance(data, dict) else None
    with _storage_lock:
        user = next((user for user in _read_store()["users"] if user["username"] == username), None)
    if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    return jsonify({"token": _make_token(user)})


@app.post("/tasks")
@jwt_required
def create_task():
    data = request.get_json(silent=True)
    title = data.get("title") if isinstance(data, dict) else None
    if not isinstance(title, str) or not title.strip():
        return jsonify({"error": "title is required"}), 400

    with _storage_lock:
        store = _read_store()
        task = {
            "id": store["next_id"],
            "title": title.strip(),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": g.current_user["id"],
        }
        store["next_id"] += 1
        store["tasks"].append(task)
        _write_store(store)
    return jsonify(task), 201


@app.get("/tasks")
@jwt_required
def list_tasks():
    with _storage_lock:
        tasks = [task for task in _read_store()["tasks"] if task.get("owner_id") == g.current_user["id"]]
    tasks.sort(key=lambda task: (task["created_at"], task["id"]), reverse=True)
    return jsonify(tasks)


@app.get("/tasks/<int:task_id>")
@jwt_required
def get_task(task_id):
    with _storage_lock:
        task = next((task for task in _read_store()["tasks"]
                     if task["id"] == task_id and task.get("owner_id") == g.current_user["id"]), None)
    return jsonify(task) if task else _not_found()


@app.put("/tasks/<int:task_id>")
@jwt_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "request body must be a JSON object"}), 400

    with _storage_lock:
        store = _read_store()
        task = next((task for task in store["tasks"]
                     if task["id"] == task_id and task.get("owner_id") == g.current_user["id"]), None)
        if task is None:
            return _not_found()
        was_completed = task.get("status") == "completed"
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip():
                return jsonify({"error": "title must be a non-empty string"}), 400
            task["title"] = data["title"].strip()
        if "status" in data:
            if not isinstance(data["status"], str) or not data["status"].strip():
                return jsonify({"error": "status must be a non-empty string"}), 400
            task["status"] = data["status"].strip()
        became_completed = task["status"] == "completed" and not was_completed
        _write_store(store)
        owner = next(
            (user for user in store["users"] if user["id"] == task.get("owner_id")),
            None,
        )
    if became_completed:
        user_email = (owner or {}).get("email") or (owner or {}).get("username")
        try:
            send_notification_email.delay(user_email, task["title"])
        except Exception:
            # A broker outage must not turn a successful task update into an error.
            app.logger.exception("Unable to queue task completion notification")
    return jsonify(task)


init_db()


if __name__ == "__main__":
    app.run()
