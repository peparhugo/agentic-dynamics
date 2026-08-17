import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

VALID_STATUSES = {"todo", "in_progress", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", "tasks.db"),
        JWT_SECRET=os.environ.get("JWT_SECRET", "change-this-secret"),
        JWT_EXPIRY_HOURS=24,
    )
    if test_config:
        app.config.update(test_config)

    app.teardown_appcontext(close_db)
    with app.app_context():
        migrate()

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify(error="bad_request", message=str(error.description)), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(error="not_found", message="Resource not found"), 404

    @app.post("/auth/register")
    def register():
        data = json_body()
        username = required_string(data, "username")
        password = required_string(data, "password")
        if len(username) < 3 or len(username) > 64:
            return error("username must be 3-64 characters")
        if len(password) < 8:
            return error("password must be at least 8 characters")
        try:
            cursor = get_db().execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            return error("username is already registered", 409)
        return jsonify(user={"id": cursor.lastrowid, "username": username}), 201

    @app.post("/auth/login")
    def login():
        data = json_body()
        username = required_string(data, "username")
        password = required_string(data, "password")
        user = get_db().execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            return error("invalid username or password", 401)
        return jsonify(access_token=make_token(user["id"]), token_type="Bearer")

    @app.get("/categories")
    @auth_required
    def list_categories():
        categories = get_db().execute(
            "SELECT id, name, owner_id, created_at FROM categories WHERE owner_id IS NULL OR owner_id = ? ORDER BY name",
            (g.user_id,),
        ).fetchall()
        return jsonify(categories=[dict(row) for row in categories])

    @app.post("/categories")
    @auth_required
    def create_category():
        name = required_string(json_body(), "name")
        try:
            cursor = get_db().execute(
                "INSERT INTO categories (name, owner_id) VALUES (?, ?)", (name, g.user_id)
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            return error("category name already exists", 409)
        category = get_db().execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(category=dict(category)), 201

    @app.get("/tasks")
    @auth_required
    def list_tasks():
        page = positive_int("page", 1)
        per_page = positive_int("per_page", 20, maximum=100)
        clauses, params = ["t.owner_id = ?"], [g.user_id]
        for field, allowed in (("status", VALID_STATUSES), ("priority", VALID_PRIORITIES)):
            value = request.args.get(field)
            if value:
                if value not in allowed:
                    return error(f"invalid {field}")
                clauses.append(f"t.{field} = ?")
                params.append(value)
        category_id = request.args.get("category_id")
        if category_id:
            try:
                params.append(int(category_id))
            except ValueError:
                return error("category_id must be an integer")
            clauses.append("t.category_id = ?")
        search = request.args.get("search")
        if search:
            clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " WHERE " + " AND ".join(clauses)
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM tasks t" + where, params).fetchone()[0]
        rows = db.execute(
            task_select() + where + " ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()
        return jsonify(tasks=[serialize_task(row) for row in rows], page=page, per_page=per_page, total=total)

    @app.post("/tasks")
    @auth_required
    def create_task():
        data = json_body()
        title = required_string(data, "title")
        values = validate_task_values(data, creating=True)
        if isinstance(values, tuple):
            return values
        cursor = get_db().execute(
            "INSERT INTO tasks (title, description, status, priority, due_date, category_id, owner_id, assignee_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (title, values["description"], values["status"], values["priority"], values["due_date"], values["category_id"], g.user_id, values["assignee_id"]),
        )
        get_db().commit()
        return jsonify(task=get_task(cursor.lastrowid)), 201

    @app.get("/tasks/<int:task_id>")
    @auth_required
    def read_task(task_id):
        task = get_task(task_id)
        if not task or task["owner_id"] != g.user_id:
            return jsonify(error="not_found", message="Resource not found"), 404
        return jsonify(task=task)

    @app.patch("/tasks/<int:task_id>")
    @auth_required
    def update_task(task_id):
        existing = get_task(task_id)
        if not existing or existing["owner_id"] != g.user_id:
            return jsonify(error="not_found", message="Resource not found"), 404
        data = json_body()
        if "title" in data and not isinstance(data["title"], str):
            return error("title must be a non-empty string")
        if "title" in data and not data["title"].strip():
            return error("title must be a non-empty string")
        values = validate_task_values(data, creating=False)
        if isinstance(values, tuple):
            return values
        updates = {key: value for key, value in values.items() if key in data}
        if "title" in data:
            updates["title"] = data["title"].strip()
        if not updates:
            return error("no updatable fields supplied")
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(f"{key} = ?" for key in updates)
        get_db().execute("UPDATE tasks SET " + assignments + " WHERE id = ?", [*updates.values(), task_id])
        get_db().commit()
        return jsonify(task=get_task(task_id))

    @app.delete("/tasks/<int:task_id>")
    @auth_required
    def delete_task(task_id):
        cursor = get_db().execute("DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.user_id))
        get_db().commit()
        if cursor.rowcount == 0:
            return jsonify(error="not_found", message="Resource not found"), 404
        return "", 204

    return app


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def migrate():
    migration = Path(__file__).parent / "migrations" / "001_initial.sql"
    get_db().executescript(migration.read_text())
    get_db().commit()


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("missing or invalid authorization token", 401)
        try:
            payload = decode_token(header[7:])
            g.user_id = int(payload["sub"])
        except Exception:
            return error("invalid or expired authorization token", 401)
        return view(*args, **kwargs)
    return wrapped


def make_token(user_id):
    payload = {"sub": user_id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"])).timestamp())}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(current_app.config["JWT_SECRET"].encode(), encoded, hashlib.sha256).digest()
    return encoded.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def decode_token(token):
    encoded, supplied_signature = token.split(".")
    expected = hmac.new(current_app.config["JWT_SECRET"].encode(), encoded.encode(), hashlib.sha256).digest()
    actual = base64.urlsafe_b64decode(supplied_signature + "=" * (-len(supplied_signature) % 4))
    if not hmac.compare_digest(expected, actual):
        raise ValueError("bad signature")
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    if payload["exp"] < datetime.now(timezone.utc).timestamp():
        raise ValueError("expired")
    return payload


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        from flask import abort
        abort(400, description="request body must be a JSON object")
    return data


def required_string(data, name):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        from flask import abort
        abort(400, description=f"{name} must be a non-empty string")
    return value.strip()


def error(message, status=400):
    return jsonify(error="validation_error", message=message), status


def positive_int(name, default, maximum=None):
    value = request.args.get(name, str(default))
    try:
        value = int(value)
    except ValueError:
        from flask import abort
        abort(400, description=f"{name} must be an integer")
    if value < 1 or (maximum and value > maximum):
        from flask import abort
        abort(400, description=f"{name} is out of range")
    return value


def validate_task_values(data, creating):
    values = {}
    defaults = {"description": "", "status": "todo", "priority": "medium", "due_date": None, "category_id": None, "assignee_id": None}
    for field, default in defaults.items():
        if field not in data:
            if creating:
                values[field] = default
            continue
        value = data[field]
        if field == "description":
            if not isinstance(value, str):
                return error("description must be a string")
        elif field == "status" and value not in VALID_STATUSES:
            return error("invalid status")
        elif field == "priority" and value not in VALID_PRIORITIES:
            return error("invalid priority")
        elif field == "due_date" and value is not None:
            if not isinstance(value, str):
                return error("due_date must be an ISO-8601 date")
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return error("due_date must be an ISO-8601 date")
        elif field in {"category_id", "assignee_id"} and value is not None:
            if not isinstance(value, int) or isinstance(value, bool):
                return error(f"{field} must be an integer or null")
            table = "categories" if field == "category_id" else "users"
            if field == "category_id":
                exists = get_db().execute(
                    "SELECT 1 FROM categories WHERE id = ? AND (owner_id IS NULL OR owner_id = ?)",
                    (value, g.user_id),
                ).fetchone()
            else:
                exists = get_db().execute("SELECT 1 FROM users WHERE id = ?", (value,)).fetchone()
            if not exists:
                return error(f"{field} does not reference an existing {table[:-1]}")
        values[field] = value
    return values


def task_select():
    return """SELECT t.*, c.name AS category_name, owner.username AS owner_username,
              assignee.username AS assignee_username FROM tasks t
              LEFT JOIN categories c ON c.id = t.category_id
              JOIN users owner ON owner.id = t.owner_id
              LEFT JOIN users assignee ON assignee.id = t.assignee_id"""


def get_task(task_id):
    row = get_db().execute(task_select() + " WHERE t.id = ?", (task_id,)).fetchone()
    return serialize_task(row) if row else None


def serialize_task(row):
    return dict(row)


if __name__ == "__main__":
    create_app().run()
