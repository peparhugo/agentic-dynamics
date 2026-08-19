"""Task management JSON API."""
import base64
import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

VALID_STATUSES = {"todo", "in_progress", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}


def _b64encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id, secret, expires_in=3600):
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({"sub": user_id, "exp": int((datetime.now(timezone.utc) + timedelta(seconds=expires_in)).timestamp())}, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token, secret):
    try:
        header, payload, signature = token.split(".")
        expected = _b64encode(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        data = json.loads(_b64decode(payload))
        if not hmac.compare_digest(signature, expected) or data["exp"] < datetime.now(timezone.utc).timestamp():
            return None
        return int(data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", "tasks.db"),
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-secret-change-me"),
        JWT_EXPIRY_SECONDS=3600,
    )
    if config:
        app.config.update(config)

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        connection = g.pop("db", None)
        if connection:
            connection.close()

    def migrate():
        connection = db()
        connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        migration_dir = Path(__file__).parent / "migrations"
        for migration in sorted(migration_dir.glob("*.sql")):
            if not connection.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (migration.name,)).fetchone():
                connection.executescript(migration.read_text())
                connection.execute("INSERT INTO schema_migrations (version) VALUES (?)", (migration.name,))
        connection.commit()

    with app.app_context():
        migrate()

    def error(message, status=400):
        return jsonify({"error": message}), status

    def payload():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else None

    def require_auth(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return error("authentication required", 401)
            user_id = decode_token(auth[7:], app.config["SECRET_KEY"])
            if not user_id or not db().execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
                return error("invalid or expired token", 401)
            g.user_id = user_id
            return view(*args, **kwargs)
        return wrapped

    def user_data(row):
        return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}

    def category_data(row):
        return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}

    def task_data(row):
        return {key: row[key] for key in row.keys()}

    def get_task(task_id, write=False):
        row = db().execute("""SELECT t.*, c.name AS category_name, owner.username AS owner_username,
                            assignee.username AS assignee_username FROM tasks t
                            LEFT JOIN categories c ON c.id = t.category_id
                            JOIN users owner ON owner.id = t.owner_id
                            LEFT JOIN users assignee ON assignee.id = t.assignee_id WHERE t.id = ?""", (task_id,)).fetchone()
        if not row or (g.user_id != row["owner_id"] and (write or g.user_id != row["assignee_id"])):
            return None
        return row

    def validate_task(data, partial=False):
        fields = {}
        if not partial and (not isinstance(data.get("title"), str) or not data["title"].strip()):
            return None, "title is required"
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip(): return None, "title must be a non-empty string"
            fields["title"] = data["title"].strip()
        if "description" in data:
            if not isinstance(data["description"], str): return None, "description must be a string"
            fields["description"] = data["description"]
        for key, valid in (("status", VALID_STATUSES), ("priority", VALID_PRIORITIES)):
            if key in data:
                if data[key] not in valid: return None, f"{key} is invalid"
                fields[key] = data[key]
        if "due_date" in data:
            value = data["due_date"]
            if value is not None:
                try: datetime.strptime(value, "%Y-%m-%d")
                except (TypeError, ValueError): return None, "due_date must be YYYY-MM-DD"
            fields["due_date"] = value
        for key in ("category_id", "assignee_id"):
            if key in data:
                value = data[key]
                if value is not None and (not isinstance(value, int) or value < 1): return None, f"{key} must be a positive integer or null"
                if key == "category_id" and value and not db().execute("SELECT 1 FROM categories WHERE id = ? AND user_id = ?", (value, g.user_id)).fetchone(): return None, "category not found"
                if key == "assignee_id" and value and not db().execute("SELECT 1 FROM users WHERE id = ?", (value,)).fetchone(): return None, "assignee not found"
                fields[key] = value
        return fields, None

    @app.post("/auth/register")
    def register():
        data = payload()
        if not data or not isinstance(data.get("username"), str) or len(data["username"].strip()) < 3 or not isinstance(data.get("password"), str) or len(data["password"]) < 8:
            return error("username (3+ chars) and password (8+ chars) are required")
        try:
            cursor = db().execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (data["username"].strip(), generate_password_hash(data["password"])))
            db().commit()
        except sqlite3.IntegrityError:
            return error("username already exists", 409)
        row = db().execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify({"user": user_data(row)}), 201

    @app.post("/auth/login")
    def login():
        data = payload() or {}
        row = db().execute("SELECT * FROM users WHERE username = ?", (data.get("username", ""),)).fetchone()
        if not row or not isinstance(data.get("password"), str) or not check_password_hash(row["password_hash"], data["password"]):
            return error("invalid username or password", 401)
        return jsonify({"token": create_token(row["id"], app.config["SECRET_KEY"], app.config["JWT_EXPIRY_SECONDS"]), "user": user_data(row)})

    @app.get("/users")
    @require_auth
    def users():
        return jsonify({"users": [user_data(row) for row in db().execute("SELECT id, username, created_at FROM users ORDER BY username")]})

    @app.route("/categories", methods=["GET", "POST"])
    @require_auth
    def categories():
        if request.method == "GET":
            return jsonify({"categories": [category_data(row) for row in db().execute("SELECT * FROM categories WHERE user_id = ? ORDER BY name", (g.user_id,))]})
        data = payload() or {}
        if not isinstance(data.get("name"), str) or not data["name"].strip(): return error("name is required")
        try:
            cursor = db().execute("INSERT INTO categories (user_id, name) VALUES (?, ?)", (g.user_id, data["name"].strip()))
            db().commit()
        except sqlite3.IntegrityError: return error("category already exists", 409)
        return jsonify({"category": category_data(db().execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone())}), 201

    @app.route("/categories/<int:category_id>", methods=["PATCH", "DELETE"])
    @require_auth
    def category(category_id):
        row = db().execute("SELECT * FROM categories WHERE id = ? AND user_id = ?", (category_id, g.user_id)).fetchone()
        if not row: return error("category not found", 404)
        if request.method == "DELETE":
            db().execute("DELETE FROM categories WHERE id = ?", (category_id,)); db().commit(); return "", 204
        data = payload() or {}
        if not isinstance(data.get("name"), str) or not data["name"].strip(): return error("name is required")
        try:
            db().execute("UPDATE categories SET name = ? WHERE id = ?", (data["name"].strip(), category_id)); db().commit()
        except sqlite3.IntegrityError: return error("category already exists", 409)
        return jsonify({"category": category_data(db().execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone())})

    @app.route("/tasks", methods=["GET", "POST"])
    @require_auth
    def tasks():
        if request.method == "POST":
            data = payload()
            if not data: return error("JSON body is required")
            fields, message = validate_task(data)
            if message: return error(message)
            columns = ["owner_id", *fields.keys()]; values = [g.user_id, *fields.values()]
            cursor = db().execute(f"INSERT INTO tasks ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", values); db().commit()
            return jsonify({"task": task_data(get_task(cursor.lastrowid))}), 201
        try:
            page, per_page = int(request.args.get("page", 1)), int(request.args.get("per_page", 20))
            if page < 1 or not 1 <= per_page <= 100: raise ValueError
        except ValueError: return error("page must be positive and per_page must be 1-100")
        clauses, values = ["(t.owner_id = ? OR t.assignee_id = ?)"], [g.user_id, g.user_id]
        filters = {"status": VALID_STATUSES, "priority": VALID_PRIORITIES}
        for name, valid in filters.items():
            if name in request.args:
                if request.args[name] not in valid: return error(f"{name} is invalid")
                clauses.append(f"t.{name} = ?"); values.append(request.args[name])
        if "category_id" in request.args:
            try: category_id = int(request.args["category_id"])
            except ValueError: return error("category_id must be an integer")
            clauses.append("t.category_id = ?"); values.append(category_id)
        if search := request.args.get("search"):
            clauses.append("(t.title LIKE ? OR t.description LIKE ?)"); values.extend([f"%{search}%", f"%{search}%"])
        where = " WHERE " + " AND ".join(clauses)
        total = db().execute("SELECT COUNT(*) FROM tasks t" + where, values).fetchone()[0]
        rows = db().execute("""SELECT t.*, c.name AS category_name, owner.username AS owner_username, assignee.username AS assignee_username FROM tasks t LEFT JOIN categories c ON c.id = t.category_id JOIN users owner ON owner.id = t.owner_id LEFT JOIN users assignee ON assignee.id = t.assignee_id""" + where + " ORDER BY t.due_date IS NULL, t.due_date, t.id DESC LIMIT ? OFFSET ?", [*values, per_page, (page - 1) * per_page]).fetchall()
        return jsonify({"tasks": [task_data(row) for row in rows], "pagination": {"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}})

    @app.route("/tasks/<int:task_id>", methods=["GET", "PATCH", "DELETE"])
    @require_auth
    def task(task_id):
        row = get_task(task_id, request.method != "GET")
        if not row: return error("task not found", 404)
        if request.method == "GET": return jsonify({"task": task_data(row)})
        if request.method == "DELETE":
            db().execute("DELETE FROM tasks WHERE id = ?", (task_id,)); db().commit(); return "", 204
        data = payload()
        if not data: return error("JSON body is required")
        fields, message = validate_task(data, partial=True)
        if message: return error(message)
        if not fields: return error("no editable fields supplied")
        assignments = ", ".join(f"{key} = ?" for key in fields) + ", updated_at = CURRENT_TIMESTAMP"
        db().execute(f"UPDATE tasks SET {assignments} WHERE id = ?", [*fields.values(), task_id]); db().commit()
        return jsonify({"task": task_data(get_task(task_id))})

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
