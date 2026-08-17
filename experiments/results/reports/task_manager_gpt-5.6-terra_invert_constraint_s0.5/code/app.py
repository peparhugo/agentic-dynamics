import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from flask import Flask, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

VALID_STATUSES = {"todo", "in_progress", "completed"}
VALID_PRIORITIES = {"low", "medium", "high"}


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


def init_db():
    migration = Path(__file__).with_name("migrations") / "001_initial.sql"
    db = get_db()
    db.executescript(migration.read_text())
    db.commit()


def error(message, status=400):
    return jsonify(error=message), status


def parse_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("due_date must be an ISO date (YYYY-MM-DD)")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ValueError("due_date must be an ISO date (YYYY-MM-DD)") from exc


def serialize_category(row):
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}


def serialize_task(row):
    return {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "status": row["status"], "priority": row["priority"], "due_date": row["due_date"],
        "category_id": row["category_id"], "category_name": row["category_name"],
        "owner_id": row["owner_id"], "assignee_id": row["assignee_id"],
        "assignee_username": row["assignee_username"], "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def task_query(where, params):
    return get_db().execute(
        "SELECT tasks.*, categories.name AS category_name, users.username AS assignee_username "
        "FROM tasks LEFT JOIN categories ON categories.id = tasks.category_id "
        "LEFT JOIN users ON users.id = tasks.assignee_id " + where, params
    )


def require_auth(handler):
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("missing or invalid authorization token", 401)
        try:
            payload = jwt.decode(header[7:], current_app.config["JWT_SECRET"], algorithms=["HS256"])
            g.user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, ValueError):
            return error("missing or invalid authorization token", 401)
        return handler(*args, **kwargs)
    wrapped.__name__ = handler.__name__
    return wrapped


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get("DATABASE", str(Path(app.instance_path) / "tasks.sqlite")),
        JWT_SECRET=os.environ.get("JWT_SECRET", "development-secret-change-me-32bytes"),
        JWT_EXPIRY_HOURS=24,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()

    @app.post("/auth/register")
    def register():
        data = request.get_json(silent=True) or {}
        username, password = data.get("username"), data.get("password")
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or len(password) < 8:
            return error("username is required and password must be at least 8 characters")
        try:
            cursor = get_db().execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                                      (username.strip(), generate_password_hash(password)))
            get_db().commit()
        except sqlite3.IntegrityError:
            return error("username is already registered", 409)
        return jsonify(id=cursor.lastrowid, username=username.strip()), 201

    @app.post("/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (data.get("username", ""),)).fetchone()
        if user is None or not isinstance(data.get("password"), str) or not check_password_hash(user["password_hash"], data["password"]):
            return error("invalid username or password", 401)
        now = datetime.now(timezone.utc)
        token = jwt.encode({"sub": str(user["id"]), "iat": now, "exp": now + timedelta(hours=app.config["JWT_EXPIRY_HOURS"])}, app.config["JWT_SECRET"], algorithm="HS256")
        return jsonify(access_token=token, token_type="Bearer")

    @app.get("/categories")
    @require_auth
    def list_categories():
        rows = get_db().execute("SELECT * FROM categories WHERE user_id = ? ORDER BY name", (g.user_id,)).fetchall()
        return jsonify(categories=[serialize_category(row) for row in rows])

    @app.post("/categories")
    @require_auth
    def create_category():
        data = request.get_json(silent=True) or {}
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return error("category name is required")
        try:
            cursor = get_db().execute("INSERT INTO categories (name, user_id) VALUES (?, ?)", (name.strip(), g.user_id))
            get_db().commit()
        except sqlite3.IntegrityError:
            return error("category already exists", 409)
        row = get_db().execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(serialize_category(row)), 201

    @app.delete("/categories/<int:category_id>")
    @require_auth
    def delete_category(category_id):
        cursor = get_db().execute("DELETE FROM categories WHERE id = ? AND user_id = ?", (category_id, g.user_id))
        get_db().commit()
        if not cursor.rowcount:
            return error("category not found", 404)
        return "", 204

    def validate_task(data, partial=False):
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        if not partial and (not isinstance(data.get("title"), str) or not data["title"].strip()):
            raise ValueError("title is required")
        values = {}
        if "title" in data:
            if not isinstance(data["title"], str) or not data["title"].strip(): raise ValueError("title must not be empty")
            values["title"] = data["title"].strip()
        if "description" in data:
            if not isinstance(data["description"], str): raise ValueError("description must be a string")
            values["description"] = data["description"]
        if "status" in data:
            if data["status"] not in VALID_STATUSES: raise ValueError("status must be todo, in_progress, or completed")
            values["status"] = data["status"]
        if "priority" in data:
            if data["priority"] not in VALID_PRIORITIES: raise ValueError("priority must be low, medium, or high")
            values["priority"] = data["priority"]
        if "due_date" in data: values["due_date"] = parse_date(data["due_date"])
        for key in ("category_id", "assignee_id"):
            if key in data:
                if data[key] is not None and (not isinstance(data[key], int) or isinstance(data[key], bool)):
                    raise ValueError(f"{key} must be an integer or null")
                values[key] = data[key]
        return values

    def validate_relationships(values):
        db = get_db()
        if values.get("category_id") is not None:
            category = db.execute("SELECT id FROM categories WHERE id = ? AND user_id = ?", (values["category_id"], g.user_id)).fetchone()
            if category is None: raise ValueError("category not found")
        if values.get("assignee_id") is not None:
            user = db.execute("SELECT id FROM users WHERE id = ?", (values["assignee_id"],)).fetchone()
            if user is None: raise ValueError("assignee not found")

    @app.post("/tasks")
    @require_auth
    def create_task():
        try:
            values = validate_task(request.get_json(silent=True), False)
            validate_relationships(values)
        except ValueError as exc:
            return error(str(exc))
        fields = ["owner_id", *values.keys()]
        cursor = get_db().execute(f"INSERT INTO tasks ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})", [g.user_id, *values.values()])
        get_db().commit()
        row = task_query("WHERE tasks.id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(serialize_task(row)), 201

    @app.get("/tasks")
    @require_auth
    def list_tasks():
        try:
            page, per_page = int(request.args.get("page", 1)), int(request.args.get("per_page", 20))
            if page < 1 or not 1 <= per_page <= 100: raise ValueError
        except ValueError:
            return error("page must be positive and per_page must be between 1 and 100")
        clauses, params = ["tasks.owner_id = ?"], [g.user_id]
        for field, allowed in (("status", VALID_STATUSES), ("priority", VALID_PRIORITIES)):
            value = request.args.get(field)
            if value:
                if value not in allowed: return error(f"invalid {field}")
                clauses.append(f"tasks.{field} = ?"); params.append(value)
        category = request.args.get("category_id")
        if category:
            try: params.append(int(category))
            except ValueError: return error("category_id must be an integer")
            clauses.append("tasks.category_id = ?")
        query = request.args.get("q")
        if query:
            clauses.append("(tasks.title LIKE ? OR tasks.description LIKE ?)"); params.extend([f"%{query}%", f"%{query}%"])
        where = " WHERE " + " AND ".join(clauses)
        total = get_db().execute("SELECT COUNT(*) FROM tasks" + where, params).fetchone()[0]
        rows = task_query(where + " ORDER BY tasks.created_at DESC, tasks.id DESC LIMIT ? OFFSET ?", [*params, per_page, (page - 1) * per_page]).fetchall()
        return jsonify(tasks=[serialize_task(row) for row in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page})

    def get_owned_task(task_id):
        row = task_query("WHERE tasks.id = ? AND tasks.owner_id = ?", (task_id, g.user_id)).fetchone()
        return row

    @app.get("/tasks/<int:task_id>")
    @require_auth
    def get_task(task_id):
        row = task_query("WHERE tasks.id = ? AND (tasks.owner_id = ? OR tasks.assignee_id = ?)", (task_id, g.user_id, g.user_id)).fetchone()
        if row is None: return error("task not found", 404)
        return jsonify(serialize_task(row))

    @app.patch("/tasks/<int:task_id>")
    @require_auth
    def update_task(task_id):
        if get_owned_task(task_id) is None: return error("task not found", 404)
        try:
            values = validate_task(request.get_json(silent=True), True)
            if not values: raise ValueError("at least one task field is required")
            validate_relationships(values)
        except ValueError as exc:
            return error(str(exc))
        assignments = ", ".join(f"{field} = ?" for field in values) + ", updated_at = CURRENT_TIMESTAMP"
        get_db().execute(f"UPDATE tasks SET {assignments} WHERE id = ?", [*values.values(), task_id])
        get_db().commit()
        return jsonify(serialize_task(get_owned_task(task_id)))

    @app.delete("/tasks/<int:task_id>")
    @require_auth
    def delete_task(task_id):
        cursor = get_db().execute("DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.user_id))
        get_db().commit()
        if not cursor.rowcount: return error("task not found", 404)
        return "", 204

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
