import os
import sqlite3
from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

DEFAULT_STATUSES = ("todo", "in_progress", "completed")
DEFAULT_PRIORITIES = ("low", "medium", "high", "urgent")


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "change-this-secret-in-production"),
        DATABASE=os.environ.get("DATABASE", os.path.join(app.instance_path, "tasks.sqlite")),
        JWT_EXPIRATION_HOURS=24,
    )
    if test_config:
        app.config.update(test_config)
    os.makedirs(app.instance_path, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    app.get_db = get_db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    def json_error(message, status=400, **extra):
        body = {"error": message}
        body.update(extra)
        return jsonify(body), status

    def token_for(user_id):
        now = datetime.now(timezone.utc)
        payload = {"sub": str(user_id), "iat": now, "exp": now.timestamp() + app.config["JWT_EXPIRATION_HOURS"] * 3600}
        return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

    def auth_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return json_error("Authorization token is required", 401)
            try:
                payload = jwt.decode(header[7:], app.config["SECRET_KEY"], algorithms=["HS256"])
                user = get_db().execute("SELECT id, username, email FROM users WHERE id = ?", (int(payload["sub"]),)).fetchone()
            except (jwt.InvalidTokenError, KeyError, ValueError):
                user = None
            if user is None:
                return json_error("Invalid or expired token", 401)
            g.user = user
            return view(*args, **kwargs)
        return wrapped

    def init_db():
        migration = os.path.join(os.path.dirname(__file__), "migrations", "001_initial.sql")
        with app.app_context():
            db = get_db()
            with open(migration, encoding="utf-8") as file:
                db.executescript(file.read())
            db.commit()

    app.init_db = init_db

    def user_json(row):
        return {"id": row["id"], "username": row["username"], "email": row["email"]}

    def task_json(row):
        result = {key: row[key] for key in ("id", "title", "description", "status", "category", "priority", "due_date", "created_at", "updated_at", "user_id", "assigned_to")}
        result["assignee"] = None if row["assignee_id"] is None else {"id": row["assignee_id"], "username": row["assignee_username"]}
        return result

    @app.post("/api/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        username, email, password = data.get("username"), data.get("email"), data.get("password")
        if not all(isinstance(value, str) and value.strip() for value in (username, email, password)):
            return json_error("username, email, and password are required")
        if len(password) < 8:
            return json_error("password must be at least 8 characters")
        db = get_db()
        try:
            cursor = db.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)", (username.strip(), email.strip().lower(), generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            return json_error("username or email already exists", 409)
        user = db.execute("SELECT id, username, email FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify({"user": user_json(user), "token": token_for(user["id"])}), 201

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        identity = data.get("username") or data.get("email")
        password = data.get("password")
        user = get_db().execute("SELECT * FROM users WHERE username = ? OR email = ?", (identity, identity)).fetchone()
        if user is None or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
            return json_error("invalid credentials", 401)
        return jsonify({"user": user_json(user), "token": token_for(user["id"]), "expires_in": app.config["JWT_EXPIRATION_HOURS"] * 3600})

    @app.get("/api/users")
    @auth_required
    def users():
        rows = get_db().execute("SELECT id, username, email FROM users ORDER BY username").fetchall()
        return jsonify({"users": [user_json(row) for row in rows]})

    def parse_task(data, partial=False):
        allowed = {"title", "description", "status", "category", "priority", "due_date", "assigned_to"}
        unknown = set(data) - allowed
        if unknown:
            return None, "unknown fields: " + ", ".join(sorted(unknown))
        if not partial and not isinstance(data.get("title"), str):
            return None, "title is required"
        values = dict(data)
        if "title" in values and (not isinstance(values["title"], str) or not values["title"].strip()):
            return None, "title must not be empty"
        if "status" in values and values["status"] not in DEFAULT_STATUSES:
            return None, "status must be one of: " + ", ".join(DEFAULT_STATUSES)
        if "priority" in values and values["priority"] not in DEFAULT_PRIORITIES:
            return None, "priority must be one of: " + ", ".join(DEFAULT_PRIORITIES)
        if "due_date" in values and values["due_date"] is not None:
            try:
                datetime.fromisoformat(values["due_date"].replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                return None, "due_date must be an ISO-8601 date or datetime"
        if "assigned_to" in values and values["assigned_to"] is not None:
            try:
                values["assigned_to"] = int(values["assigned_to"])
            except (TypeError, ValueError):
                return None, "assigned_to must be a user id"
            if get_db().execute("SELECT id FROM users WHERE id = ?", (values["assigned_to"],)).fetchone() is None:
                return None, "assigned user does not exist"
        return values, None

    task_select = "SELECT t.*, u.username AS assignee_username, u.id AS assignee_id FROM tasks t LEFT JOIN users u ON u.id = t.assigned_to"

    @app.route("/api/tasks", methods=["GET", "POST"])
    @auth_required
    def task_collection():
        db = get_db()
        if request.method == "POST":
            values, error = parse_task(request.get_json(silent=True) or {})
            if error:
                return json_error(error)
            now = datetime.now(timezone.utc).isoformat()
            values.setdefault("description", "")
            values.setdefault("status", "todo")
            values.setdefault("category", "general")
            values.setdefault("priority", "medium")
            values.setdefault("due_date", None)
            values.setdefault("assigned_to", None)
            cursor = db.execute("INSERT INTO tasks (title, description, status, category, priority, due_date, user_id, assigned_to, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (values["title"].strip(), values["description"], values["status"], values["category"], values["priority"], values["due_date"], g.user["id"], values["assigned_to"], now, now))
            db.commit()
            return jsonify(task_json(db.execute(task_select + " WHERE t.id = ?", (cursor.lastrowid,)).fetchone())), 201
        clauses, params = [], []
        for field in ("status", "category", "priority"):
            if request.args.get(field):
                clauses.append("t." + field + " = ?")
                params.append(request.args[field])
        search = request.args.get("search", request.args.get("q"))
        if search:
            clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        try:
            page, per_page = max(1, int(request.args.get("page", 1))), min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return json_error("page and per_page must be integers")
        total = db.execute("SELECT COUNT(*) FROM tasks t" + where, params).fetchone()[0]
        rows = db.execute(task_select + where + " ORDER BY t.due_date IS NULL, t.due_date, t.created_at DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
        return jsonify({"tasks": [task_json(row) for row in rows], "pagination": {"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}})

    @app.route("/api/tasks/<int:task_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
    @auth_required
    def task_item(task_id):
        db = get_db()
        row = db.execute(task_select + " WHERE t.id = ?", (task_id,)).fetchone()
        if row is None:
            return json_error("task not found", 404)
        if request.method == "GET":
            return jsonify(task_json(row))
        if request.method == "DELETE":
            db.execute("DELETE FROM tasks WHERE id = ?", (task_id,)); db.commit()
            return "", 204
        values, error = parse_task(request.get_json(silent=True) or {}, partial=request.method == "PATCH")
        if error:
            return json_error(error)
        if not values:
            return jsonify(task_json(row))
        values["updated_at"] = datetime.now(timezone.utc).isoformat()
        assignments = ", ".join(key + " = ?" for key in values)
        db.execute("UPDATE tasks SET " + assignments + " WHERE id = ?", list(values.values()) + [task_id]); db.commit()
        return jsonify(task_json(db.execute(task_select + " WHERE t.id = ?", (task_id,)).fetchone()))

    @app.get("/api/categories")
    @auth_required
    def categories():
        rows = get_db().execute("SELECT category, COUNT(*) AS count FROM tasks GROUP BY category ORDER BY category").fetchall()
        return jsonify({"categories": [{"name": row["category"], "count": row["count"]} for row in rows]})

    with app.app_context():
        init_db()
    return app
