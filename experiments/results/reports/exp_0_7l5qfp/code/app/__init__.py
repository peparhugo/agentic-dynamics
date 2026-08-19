import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA = BASE_DIR / "migrations" / "001_initial.sql"


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
        DATABASE=os.environ.get("DATABASE", str(BASE_DIR / "task_manager.sqlite3")),
        JWT_EXPIRY_HOURS=24,
    )
    if test_config:
        app.config.update(test_config)

    @app.cli.command("init-db")
    def init_db_command():
        """Create the SQLite schema."""
        init_db(app)
        print("initialized database")

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.errorhandler(404)
    def not_found(_error):
        return error("resource not found", 404)

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return error("method not allowed", 405)

    register_routes(app)
    return app


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.app.config["DATABASE"] if hasattr(g, "app") else current_app().config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def current_app():
    from flask import current_app as flask_current_app
    return flask_current_app


def init_db(app):
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA.read_text())
        db.commit()


def error(message, status=400):
    return jsonify(error=message), status


def token_for(user):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user["id"]), "email": user["email"], "iat": now, "exp": now + timedelta(hours=current_app().config["JWT_EXPIRY_HOURS"])}
    return jwt.encode(payload, current_app().config["SECRET_KEY"], algorithm="HS256")


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("missing bearer token", 401)
        try:
            payload = jwt.decode(header[7:], current_app().config["SECRET_KEY"], algorithms=["HS256"])
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return error("invalid or expired token", 401)
        user = get_db().execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return error("user not found", 401)
        g.user = user
        return view(*args, **kwargs)
    return wrapped


def parse_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error("request body must be a JSON object", 400)
    return data, None


def serialize_task(row):
    task = dict(row)
    task["assigned_to"] = task.pop("assigned_to_id")
    return task


def validate_task_fields(data, partial=False):
    allowed = {"title", "description", "status", "category", "priority", "due_date", "assigned_to"}
    unknown = set(data) - allowed
    if unknown:
        return f"unknown fields: {', '.join(sorted(unknown))}"
    if not partial and not data.get("title"):
        return "title is required"
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip() or len(data["title"]) > 200):
        return "title must be a non-empty string of at most 200 characters"
    if "description" in data and data["description"] is not None and not isinstance(data["description"], str):
        return "description must be a string or null"
    if "status" in data and data["status"] not in {"todo", "in_progress", "done"}:
        return "status must be todo, in_progress, or done"
    if "priority" in data and data["priority"] not in {"low", "medium", "high"}:
        return "priority must be low, medium, or high"
    if "category" in data and data["category"] is not None and (not isinstance(data["category"], str) or len(data["category"]) > 100):
        return "category must be a string of at most 100 characters or null"
    if "due_date" in data and data["due_date"] is not None:
        try:
            datetime.strptime(data["due_date"], "%Y-%m-%d")
        except (TypeError, ValueError):
            return "due_date must use YYYY-MM-DD format or be null"
    if "assigned_to" in data and data["assigned_to"] is not None:
        if not isinstance(data["assigned_to"], int) or data["assigned_to"] <= 0:
            return "assigned_to must be a positive integer or null"
    return None


def register_routes(app):
    @app.post("/api/auth/register")
    def register():
        data, response = parse_json()
        if response:
            return response
        email = data.get("email")
        password = data.get("password")
        if not isinstance(email, str) or not email.strip() or "@" not in email:
            return error("a valid email is required")
        if not isinstance(password, str) or len(password) < 8:
            return error("password must be at least 8 characters")
        db = get_db()
        try:
            cursor = db.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email.strip().lower(), generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            return error("email is already registered", 409)
        user = db.execute("SELECT id, email FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(user=dict(user), token=token_for(user)), 201

    @app.post("/api/auth/login")
    def login():
        data, response = parse_json()
        if response:
            return response
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (str(data.get("email", "")).strip().lower(),)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], str(data.get("password", ""))):
            return error("invalid email or password", 401)
        return jsonify(user={"id": user["id"], "email": user["email"]}, token=token_for(user))

    @app.get("/api/tasks")
    @auth_required
    def list_tasks():
        db = get_db()
        clauses = ["(t.owner_id = ? OR t.assigned_to_id = ?)"]
        params = [g.user["id"], g.user["id"]]
        for field in ("status", "category", "priority"):
            value = request.args.get(field)
            if value:
                clauses.append(f"t.{field} = ?")
                params.append(value)
        search = request.args.get("search", "").strip()
        if search:
            clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return error("page and per_page must be integers")
        where = " AND ".join(clauses)
        total = db.execute(f"SELECT COUNT(*) FROM tasks t WHERE {where}", params).fetchone()[0]
        rows = db.execute(f"SELECT t.id, t.title, t.description, t.status, t.category, t.priority, t.due_date, t.owner_id, t.assigned_to_id, t.created_at, t.updated_at FROM tasks t WHERE {where} ORDER BY t.due_date IS NULL, t.due_date, t.created_at DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
        return jsonify(tasks=[serialize_task(row) for row in rows], page=page, per_page=per_page, total=total, pages=(total + per_page - 1) // per_page)

    @app.post("/api/tasks")
    @auth_required
    def create_task():
        data, response = parse_json()
        if response:
            return response
        message = validate_task_fields(data)
        if message:
            return error(message)
        assigned = data.get("assigned_to")
        db = get_db()
        if assigned is not None and db.execute("SELECT 1 FROM users WHERE id = ?", (assigned,)).fetchone() is None:
            return error("assigned user not found")
        cursor = db.execute("INSERT INTO tasks (title, description, status, category, priority, due_date, owner_id, assigned_to_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (data["title"].strip(), data.get("description"), data.get("status", "todo"), data.get("category"), data.get("priority", "medium"), data.get("due_date"), g.user["id"], assigned))
        db.commit()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(task=serialize_task(row)), 201

    @app.route("/api/tasks/<int:task_id>", methods=["GET", "PATCH", "PUT", "DELETE"])
    @auth_required
    def task_detail(task_id):
        db = get_db()
        row = db.execute("SELECT * FROM tasks WHERE id = ? AND (owner_id = ? OR assigned_to_id = ?)", (task_id, g.user["id"], g.user["id"])).fetchone()
        if row is None:
            return error("task not found", 404)
        if request.method == "GET":
            return jsonify(task=serialize_task(row))
        if row["owner_id"] != g.user["id"]:
            return error("only the task owner may modify it", 403)
        if request.method == "DELETE":
            db.execute("DELETE FROM tasks WHERE id = ?", (task_id,)); db.commit()
            return "", 204
        data, response = parse_json()
        if response:
            return response
        message = validate_task_fields(data, partial=True)
        if message:
            return error(message)
        if "assigned_to" in data and data["assigned_to"] is not None and db.execute("SELECT 1 FROM users WHERE id = ?", (data["assigned_to"],)).fetchone() is None:
            return error("assigned user not found")
        columns = {"title": "title", "description": "description", "status": "status", "category": "category", "priority": "priority", "due_date": "due_date", "assigned_to": "assigned_to_id"}
        if not data:
            return error("at least one field is required")
        assignments = ", ".join(f"{columns[key]} = ?" for key in data)
        values = [data[key].strip() if key == "title" else data[key] for key in data] + [task_id]
        db.execute(f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values); db.commit()
        return jsonify(task=serialize_task(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()))
