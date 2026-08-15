from datetime import date

from flask import Blueprint, g, jsonify, request

from .auth import error, require_auth
from .database import get_db

api_bp = Blueprint("api", __name__)
STATUSES = {"todo", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def task_json(row):
    return {key: row[key] for key in ("id", "title", "description", "status", "priority", "due_date", "category_id", "owner_id", "assigned_to", "created_at", "updated_at")}


def valid_date(value):
    if value is None:
        return True
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def user_exists(db, user_id):
    return isinstance(user_id, int) and db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is not None


def validate_task(data, db, partial=False):
    if not partial and (not isinstance(data.get("title"), str) or not data["title"].strip()):
        return "title is required"
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return "title must be a non-empty string"
    if "status" in data and data["status"] not in STATUSES:
        return "invalid status"
    if "priority" in data and data["priority"] not in PRIORITIES:
        return "invalid priority"
    if "due_date" in data and not valid_date(data["due_date"]):
        return "due_date must be an ISO date"
    if "assigned_to" in data and data["assigned_to"] is not None and not user_exists(db, data["assigned_to"]):
        return "assigned_to must reference an existing user"
    if "category_id" in data and data["category_id"] is not None:
        category = db.execute("SELECT 1 FROM categories WHERE id = ? AND owner_id = ?", (data["category_id"], g.current_user_id)).fetchone()
        if category is None:
            return "category_id must reference one of your categories"
    return None


@api_bp.route("/categories", methods=["GET", "POST"])
@require_auth
def categories():
    db = get_db()
    if request.method == "GET":
        rows = db.execute("SELECT id, name, created_at FROM categories WHERE owner_id = ? ORDER BY name", (g.current_user_id,)).fetchall()
        return jsonify({"categories": [dict(row) for row in rows]})
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return error("category name is required")
    try:
        cursor = db.execute("INSERT INTO categories (name, owner_id) VALUES (?, ?)", (name, g.current_user_id))
        db.commit()
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return error("category already exists", 409)
        raise
    row = db.execute("SELECT id, name, created_at FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"category": dict(row)}), 201


@api_bp.post("/tasks")
@require_auth
def create_task():
    data = request.get_json(silent=True) or {}
    db = get_db()
    message = validate_task(data, db)
    if message:
        return error(message)
    cursor = db.execute(
        """INSERT INTO tasks (title, description, status, priority, due_date, category_id, owner_id, assigned_to)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (data["title"].strip(), data.get("description"), data.get("status", "todo"), data.get("priority", "medium"), data.get("due_date"), data.get("category_id"), g.current_user_id, data.get("assigned_to")),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"task": task_json(row)}), 201


@api_bp.get("/tasks")
@require_auth
def list_tasks():
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        return error("page and per_page must be integers")
    filters, params = ["(owner_id = ? OR assigned_to = ?)"], [g.current_user_id, g.current_user_id]
    for key in ("status", "priority", "category_id"):
        value = request.args.get(key)
        if value is not None:
            if key == "status" and value not in STATUSES:
                return error("invalid status")
            if key == "priority" and value not in PRIORITIES:
                return error("invalid priority")
            if key == "category_id":
                try:
                    value = int(value)
                except ValueError:
                    return error("category_id must be an integer")
            filters.append(f"{key} = ?")
            params.append(value)
    if request.args.get("search"):
        filters.append("(title LIKE ? OR COALESCE(description, '') LIKE ?)")
        needle = f"%{request.args['search']}%"
        params.extend([needle, needle])
    where = " WHERE " + " AND ".join(filters)
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM tasks" + where, params).fetchone()[0]
    rows = db.execute("SELECT * FROM tasks" + where + " ORDER BY due_date IS NULL, due_date, id DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
    return jsonify({"tasks": [task_json(row) for row in rows], "pagination": {"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page}})


def owned_task(task_id):
    return get_db().execute("SELECT * FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.current_user_id)).fetchone()


@api_bp.route("/tasks/<int:task_id>", methods=["GET", "PATCH", "DELETE"])
@require_auth
def task_detail(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ? AND (owner_id = ? OR assigned_to = ?)", (task_id, g.current_user_id, g.current_user_id)).fetchone()
    if task is None:
        return error("task not found", 404)
    if request.method == "GET":
        return jsonify({"task": task_json(task)})
    if task["owner_id"] != g.current_user_id:
        return error("only the task owner may modify or delete it", 403)
    if request.method == "DELETE":
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        return "", 204
    data = request.get_json(silent=True) or {}
    allowed = {"title", "description", "status", "priority", "due_date", "category_id", "assigned_to"}
    data = {key: value for key, value in data.items() if key in allowed}
    if not data:
        return error("no updatable fields supplied")
    message = validate_task(data, db, partial=True)
    if message:
        return error(message)
    columns = ", ".join(f"{key} = ?" for key in data)
    values = [value.strip() if key == "title" else value for key, value in data.items()]
    db.execute(f"UPDATE tasks SET {columns}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values + [task_id])
    db.commit()
    return jsonify({"task": task_json(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())})
