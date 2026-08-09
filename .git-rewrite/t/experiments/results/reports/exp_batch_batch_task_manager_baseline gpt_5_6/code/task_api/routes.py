import math
import sqlite3
from datetime import date

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import auth_required, create_token
from .db import get_db

api = Blueprint("api", __name__, url_prefix="/api")
STATUSES = {"pending", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def body():
    return request.get_json(silent=True) or {}


def user_json(row):
    return {"id": row["id"], "username": row["username"], "email": row["email"]}


def category_json(row):
    return {"id": row["id"], "name": row["name"], "created_at": row["created_at"]}


def task_query(where=""):
    return f"""
        SELECT t.*, c.name category_name,
               a.username assigned_username, o.username creator_username
        FROM tasks t
        LEFT JOIN categories c ON c.id = t.category_id
        LEFT JOIN users a ON a.id = t.assigned_to
        JOIN users o ON o.id = t.created_by
        {where}
    """


def task_json(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"],
        "category": (
            {"id": row["category_id"], "name": row["category_name"]}
            if row["category_id"] is not None
            else None
        ),
        "assigned_to": (
            {"id": row["assigned_to"], "username": row["assigned_username"]}
            if row["assigned_to"] is not None
            else None
        ),
        "created_by": {"id": row["created_by"], "username": row["creator_username"]},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def validate_task(data, partial=False):
    errors = {}
    if not partial or "title" in data:
        if not isinstance(data.get("title"), str) or not data["title"].strip():
            errors["title"] = "title is required"
    if "description" in data and not isinstance(data["description"], str):
        errors["description"] = "description must be a string"
    if "status" in data and data["status"] not in STATUSES:
        errors["status"] = "must be pending, in_progress, or completed"
    if "priority" in data and data["priority"] not in PRIORITIES:
        errors["priority"] = "must be low, medium, high, or urgent"
    if data.get("due_date") is not None:
        try:
            date.fromisoformat(data["due_date"])
        except (TypeError, ValueError):
            errors["due_date"] = "must be an ISO date (YYYY-MM-DD)"
    return errors


def validate_relations(data, creator_id):
    db = get_db()
    if data.get("category_id") is not None:
        category = db.execute(
            "SELECT id FROM categories WHERE id = ? AND user_id = ?",
            (data["category_id"], creator_id),
        ).fetchone()
        if category is None:
            return "category not found"
    if data.get("assigned_to") is not None:
        assignee = db.execute("SELECT id FROM users WHERE id = ?", (data["assigned_to"],)).fetchone()
        if assignee is None:
            return "assigned user not found"
    return None


@api.post("/auth/register")
def register():
    data = body()
    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    errors = {}
    if not isinstance(username, str) or len(username.strip()) < 3:
        errors["username"] = "must be at least 3 characters"
    if not isinstance(email, str) or "@" not in email:
        errors["email"] = "must be a valid email address"
    if not isinstance(password, str) or len(password) < 8:
        errors["password"] = "must be at least 8 characters"
    if errors:
        return jsonify(error="validation failed", details=errors), 400

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username.strip(), email.strip().lower(), generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="username or email already exists"), 409
    user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(user=user_json(user), token=create_token(user["id"])), 201


@api.post("/auth/login")
def login():
    data = body()
    identity = data.get("email") or data.get("username") or ""
    user = get_db().execute(
        "SELECT * FROM users WHERE email = ? COLLATE NOCASE OR username = ? COLLATE NOCASE",
        (identity, identity),
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], data.get("password", "")):
        return jsonify(error="invalid credentials"), 401
    return jsonify(user=user_json(user), token=create_token(user["id"]))


@api.get("/users")
@auth_required
def list_users():
    rows = get_db().execute("SELECT * FROM users ORDER BY username COLLATE NOCASE").fetchall()
    return jsonify(users=[user_json(row) for row in rows])


@api.get("/auth/me")
@auth_required
def me():
    return jsonify(user=user_json(g.user))


@api.route("/categories", methods=["GET", "POST"])
@auth_required
def categories():
    db = get_db()
    if request.method == "GET":
        rows = db.execute(
            "SELECT * FROM categories WHERE user_id = ? ORDER BY name COLLATE NOCASE", (g.user["id"],)
        ).fetchall()
        return jsonify(categories=[category_json(row) for row in rows])

    name = body().get("name", "")
    if not isinstance(name, str) or not name.strip():
        return jsonify(error="validation failed", details={"name": "name is required"}), 400
    try:
        cursor = db.execute(
            "INSERT INTO categories (name, user_id) VALUES (?, ?)", (name.strip(), g.user["id"])
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="category already exists"), 409
    row = db.execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(category=category_json(row)), 201


@api.route("/categories/<int:category_id>", methods=["GET", "PATCH", "PUT", "DELETE"])
@auth_required
def category_detail(category_id):
    db = get_db()
    row = db.execute(
        "SELECT * FROM categories WHERE id = ? AND user_id = ?", (category_id, g.user["id"])
    ).fetchone()
    if row is None:
        return jsonify(error="category not found"), 404
    if request.method == "GET":
        return jsonify(category=category_json(row))
    if request.method == "DELETE":
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        db.commit()
        return "", 204

    name = body().get("name", "")
    if not isinstance(name, str) or not name.strip():
        return jsonify(error="validation failed", details={"name": "name is required"}), 400
    try:
        db.execute("UPDATE categories SET name = ? WHERE id = ?", (name.strip(), category_id))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="category already exists"), 409
    row = db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    return jsonify(category=category_json(row))


@api.route("/tasks", methods=["GET", "POST"])
@auth_required
def tasks():
    db = get_db()
    if request.method == "POST":
        data = body()
        errors = validate_task(data)
        if errors:
            return jsonify(error="validation failed", details=errors), 400
        relation_error = validate_relations(data, g.user["id"])
        if relation_error:
            return jsonify(error=relation_error), 400
        cursor = db.execute(
            """INSERT INTO tasks
               (title, description, status, priority, due_date, category_id, assigned_to, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["title"].strip(), data.get("description", ""), data.get("status", "pending"),
                data.get("priority", "medium"), data.get("due_date"), data.get("category_id"),
                data.get("assigned_to"), g.user["id"],
            ),
        )
        db.commit()
        row = db.execute(task_query("WHERE t.id = ?"), (cursor.lastrowid,)).fetchone()
        return jsonify(task=task_json(row)), 201

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify(error="page and per_page must be integers"), 400
    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify(error="page must be positive and per_page must be between 1 and 100"), 400

    clauses = ["(t.created_by = ? OR t.assigned_to = ?)"]
    params = [g.user["id"], g.user["id"]]
    for field, allowed in (("status", STATUSES), ("priority", PRIORITIES)):
        value = request.args.get(field)
        if value:
            if value not in allowed:
                return jsonify(error=f"invalid {field}"), 400
            clauses.append(f"t.{field} = ?")
            params.append(value)
    category_id = request.args.get("category_id") or request.args.get("category")
    if category_id:
        try:
            category_id = int(category_id)
        except ValueError:
            return jsonify(error="category_id must be an integer"), 400
        clauses.append("t.category_id = ?")
        params.append(category_id)
    assigned_to = request.args.get("assigned_to")
    if assigned_to:
        try:
            assigned_to = int(assigned_to)
        except ValueError:
            return jsonify(error="assigned_to must be an integer"), 400
        clauses.append("t.assigned_to = ?")
        params.append(assigned_to)
    search = request.args.get("search") or request.args.get("q")
    if search:
        clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " WHERE " + " AND ".join(clauses)
    total = db.execute("SELECT COUNT(*) FROM tasks t" + where, params).fetchone()[0]
    rows = db.execute(
        task_query(where) + " ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?",
        (*params, per_page, (page - 1) * per_page),
    ).fetchall()
    return jsonify(
        tasks=[task_json(row) for row in rows],
        pagination={
            "page": page, "per_page": per_page, "total": total,
            "pages": math.ceil(total / per_page),
        },
    )


@api.route("/tasks/<int:task_id>", methods=["GET", "PATCH", "PUT", "DELETE"])
@auth_required
def task_detail(task_id):
    db = get_db()
    row = db.execute(
        task_query("WHERE t.id = ? AND (t.created_by = ? OR t.assigned_to = ?)"),
        (task_id, g.user["id"], g.user["id"]),
    ).fetchone()
    if row is None:
        return jsonify(error="task not found"), 404
    if request.method == "GET":
        return jsonify(task=task_json(row))
    if row["created_by"] != g.user["id"]:
        return jsonify(error="only the task creator may modify this task"), 403
    if request.method == "DELETE":
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        return "", 204

    data = body()
    errors = validate_task(data, partial=request.method == "PATCH")
    if errors:
        return jsonify(error="validation failed", details=errors), 400
    relation_error = validate_relations(data, g.user["id"])
    if relation_error:
        return jsonify(error=relation_error), 400
    allowed = {"title", "description", "status", "priority", "due_date", "category_id", "assigned_to"}
    updates = {key: value for key, value in data.items() if key in allowed}
    if "title" in updates:
        updates["title"] = updates["title"].strip()
    if not updates:
        return jsonify(error="no task fields supplied"), 400
    assignments = ", ".join(f"{key} = ?" for key in updates)
    db.execute(
        f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (*updates.values(), task_id),
    )
    db.commit()
    row = db.execute(task_query("WHERE t.id = ?"), (task_id,)).fetchone()
    return jsonify(task=task_json(row))
