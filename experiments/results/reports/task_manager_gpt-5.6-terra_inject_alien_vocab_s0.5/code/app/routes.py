from datetime import date

from flask import Blueprint, g, jsonify, request

from .auth import auth_required, create_token, hash_password, verify_password
from .db import get_db

api = Blueprint("api", __name__)
STATUSES = {"todo", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def error(message, code=400):
    return jsonify(error=message), code


def body():
    value = request.get_json(silent=True)
    return value if isinstance(value, dict) else None


def parse_task(data, partial=False):
    allowed = {"title", "description", "status", "category", "priority", "due_date", "assignee_id"}
    unknown = set(data) - allowed
    if unknown:
        return None, f"unknown fields: {', '.join(sorted(unknown))}"
    result = {}
    if not partial and (not isinstance(data.get("title"), str) or not data["title"].strip()):
        return None, "title is required"
    for key in ("title", "description", "category"):
        if key in data:
            if not isinstance(data[key], str):
                return None, f"{key} must be a string"
            result[key] = data[key].strip() if key == "title" else data[key]
    if "title" in result and not result["title"]:
        return None, "title is required"
    for key, choices in (("status", STATUSES), ("priority", PRIORITIES)):
        if key in data:
            if data[key] not in choices:
                return None, f"{key} must be one of: {', '.join(sorted(choices))}"
            result[key] = data[key]
    if "due_date" in data:
        if data["due_date"] is not None:
            try:
                date.fromisoformat(data["due_date"])
            except (TypeError, ValueError):
                return None, "due_date must be an ISO date"
        result["due_date"] = data["due_date"]
    if "assignee_id" in data:
        if data["assignee_id"] is not None and (not isinstance(data["assignee_id"], int) or isinstance(data["assignee_id"], bool)):
            return None, "assignee_id must be an integer or null"
        result["assignee_id"] = data["assignee_id"]
    return result, None


def task_json(row):
    return dict(row)


@api.post("/auth/register")
def register():
    data = body()
    if not data or set(data) - {"email", "password", "name"} or not all(isinstance(data.get(k), str) and data[k].strip() for k in ("email", "password", "name")):
        return error("email, password, and name are required")
    if len(data["password"]) < 8:
        return error("password must be at least 8 characters")
    db = get_db()
    try:
        cursor = db.execute("INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)", (data["email"].lower().strip(), data["name"].strip(), hash_password(data["password"])))
        db.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc):
            return error("email is already registered", 409)
        raise
    user = {"id": cursor.lastrowid, "email": data["email"].lower().strip(), "name": data["name"].strip()}
    return jsonify(user=user, token=create_token(user["id"])), 201


@api.post("/auth/login")
def login():
    data = body() or {}
    if not isinstance(data.get("email"), str) or not isinstance(data.get("password"), str):
        return error("email and password are required")
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (data["email"].lower().strip(),)).fetchone()
    if user is None or not verify_password(data["password"], user["password_hash"]):
        return error("invalid email or password", 401)
    return jsonify(user={"id": user["id"], "email": user["email"], "name": user["name"]}, token=create_token(user["id"]))


@api.get("/tasks")
@auth_required
def list_tasks():
    try:
        page, per_page = int(request.args.get("page", 1)), int(request.args.get("per_page", 20))
    except ValueError:
        return error("page and per_page must be integers")
    if page < 1 or not 1 <= per_page <= 100:
        return error("page must be positive and per_page must be 1 through 100")
    clauses, params = ["(t.owner_id = ? OR t.assignee_id = ?)"], [g.current_user["id"], g.current_user["id"]]
    for key, choices in (("status", STATUSES), ("priority", PRIORITIES)):
        value = request.args.get(key)
        if value:
            if value not in choices:
                return error(f"invalid {key}")
            clauses.append(f"t.{key} = ?")
            params.append(value)
    if request.args.get("category"):
        clauses.append("t.category = ?")
        params.append(request.args["category"])
    if request.args.get("search"):
        clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
        term = f"%{request.args['search']}%"
        params.extend([term, term])
    where = " WHERE " + " AND ".join(clauses)
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM tasks t" + where, params).fetchone()[0]
    rows = db.execute("SELECT t.*, u.email AS assignee_email FROM tasks t LEFT JOIN users u ON t.assignee_id = u.id" + where + " ORDER BY t.id DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
    return jsonify(tasks=[task_json(row) for row in rows], page=page, per_page=per_page, total=total)


@api.post("/tasks")
@auth_required
def create_task():
    data = body()
    if data is None:
        return error("JSON object required")
    values, issue = parse_task(data)
    if issue:
        return error(issue)
    values.setdefault("description", "")
    values.setdefault("status", "todo")
    values.setdefault("category", None)
    values.setdefault("priority", "medium")
    values.setdefault("due_date", None)
    values.setdefault("assignee_id", None)
    db = get_db()
    if values["assignee_id"] is not None and db.execute("SELECT 1 FROM users WHERE id = ?", (values["assignee_id"],)).fetchone() is None:
        return error("assignee does not exist")
    cursor = db.execute(
        "INSERT INTO tasks (title, description, status, category, priority, due_date, owner_id, assignee_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (values["title"], values["description"], values["status"], values["category"], values["priority"], values["due_date"], g.current_user["id"], values["assignee_id"]),
    )
    db.commit()
    row = db.execute("SELECT t.*, u.email AS assignee_email FROM tasks t LEFT JOIN users u ON t.assignee_id = u.id WHERE t.id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(task=task_json(row)), 201


def owner_task(task_id):
    return get_db().execute("SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.current_user["id"])).fetchone()


@api.get("/tasks/<int:task_id>")
@auth_required
def get_task(task_id):
    row = get_db().execute("SELECT t.*, u.email AS assignee_email FROM tasks t LEFT JOIN users u ON t.assignee_id = u.id WHERE t.id = ? AND (t.owner_id = ? OR t.assignee_id = ?)", (task_id, g.current_user["id"], g.current_user["id"])).fetchone()
    return jsonify(task=task_json(row)) if row else error("task not found", 404)


@api.patch("/tasks/<int:task_id>")
@auth_required
def update_task(task_id):
    if owner_task(task_id) is None:
        return error("task not found", 404)
    data = body()
    if data is None:
        return error("JSON object required")
    values, issue = parse_task(data, partial=True)
    if issue:
        return error(issue)
    if not values:
        return error("no fields to update")
    db = get_db()
    if "assignee_id" in values and values["assignee_id"] is not None and db.execute("SELECT 1 FROM users WHERE id = ?", (values["assignee_id"],)).fetchone() is None:
        return error("assignee does not exist")
    assignments = ", ".join(f"{key} = ?" for key in values)
    db.execute(f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [*values.values(), task_id])
    db.commit()
    row = db.execute("SELECT t.*, u.email AS assignee_email FROM tasks t LEFT JOIN users u ON t.assignee_id = u.id WHERE t.id = ?", (task_id,)).fetchone()
    return jsonify(task=task_json(row))


@api.delete("/tasks/<int:task_id>")
@auth_required
def delete_task(task_id):
    if owner_task(task_id) is None:
        return error("task not found", 404)
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return "", 204
