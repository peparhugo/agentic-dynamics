import sqlite3

from flask import Blueprint, g, jsonify, request

from .common import (
    PRIORITIES,
    STATUSES,
    TASK_SELECT,
    auth_required,
    error,
    json_body,
    normalize_due_date,
    serialize_task,
)
from .db import get_db


tasks_bp = Blueprint("tasks", __name__)


def validate_reference(db, table, value, user_id=None):
    if value is None:
        return True
    if not isinstance(value, int) or isinstance(value, bool):
        return False
    if table == "categories":
        row = db.execute(
            "SELECT id FROM categories WHERE id = ? AND user_id = ?", (value, user_id)
        ).fetchone()
    else:
        row = db.execute("SELECT id FROM users WHERE id = ?", (value,)).fetchone()
    return row is not None


def validate_task(data, partial=False):
    if not partial or "title" in data:
        if not isinstance(data.get("title"), str) or not data["title"].strip():
            return "title is required"
    if "description" in data and data["description"] is not None and not isinstance(data["description"], str):
        return "description must be a string or null"
    if "status" in data and data["status"] not in STATUSES:
        return f"status must be one of: {', '.join(STATUSES)}"
    if "priority" in data and data["priority"] not in PRIORITIES:
        return f"priority must be one of: {', '.join(PRIORITIES)}"
    if "due_date" in data:
        try:
            data["due_date"] = normalize_due_date(data["due_date"])
        except ValueError as exc:
            return str(exc)
    return None


@tasks_bp.post("")
@auth_required
def create_task():
    data, response = json_body()
    if response:
        return response
    message = validate_task(data)
    if message:
        return error(message)
    db = get_db()
    category_id = data.get("category_id")
    assignee_id = data.get("assignee_id")
    if not validate_reference(db, "categories", category_id, g.user["id"]):
        return error("category not found", 404)
    if not validate_reference(db, "users", assignee_id):
        return error("assignee not found", 404)
    cursor = db.execute(
        """INSERT INTO tasks
           (title, description, status, priority, due_date, category_id, creator_id, assignee_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["title"].strip(),
            data.get("description"),
            data.get("status", "pending"),
            data.get("priority", "medium"),
            data.get("due_date"),
            category_id,
            g.user["id"],
            assignee_id,
        ),
    )
    db.commit()
    row = db.execute(TASK_SELECT + " WHERE t.id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(serialize_task(row)), 201


@tasks_bp.get("")
@auth_required
def list_tasks():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return error("page and per_page must be integers")
    if page < 1 or per_page < 1 or per_page > 100:
        return error("page must be >= 1 and per_page must be between 1 and 100")

    clauses = ["(t.creator_id = ? OR t.assignee_id = ?)"]
    params = [g.user["id"], g.user["id"]]
    for field, allowed in (("status", STATUSES), ("priority", PRIORITIES)):
        value = request.args.get(field)
        if value:
            if value not in allowed:
                return error(f"{field} must be one of: {', '.join(allowed)}")
            clauses.append(f"t.{field} = ?")
            params.append(value)
    category = request.args.get("category")
    if category:
        clauses.append("c.name = ?")
        params.append(category)
    query = request.args.get("q")
    if query:
        clauses.append("(t.title LIKE ? OR COALESCE(t.description, '') LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])

    where = " WHERE " + " AND ".join(clauses)
    db = get_db()
    total = db.execute(
        "SELECT COUNT(*) FROM tasks t LEFT JOIN categories c ON c.id = t.category_id" + where,
        params,
    ).fetchone()[0]
    rows = db.execute(
        TASK_SELECT + where + " ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?",
        (*params, per_page, (page - 1) * per_page),
    ).fetchall()
    return jsonify(
        items=[serialize_task(row) for row in rows],
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    )


@tasks_bp.get("/<int:task_id>")
@auth_required
def get_task(task_id):
    row = get_db().execute(
        TASK_SELECT + " WHERE t.id = ? AND (t.creator_id = ? OR t.assignee_id = ?)",
        (task_id, g.user["id"], g.user["id"]),
    ).fetchone()
    if row is None:
        return error("task not found", 404)
    return jsonify(serialize_task(row))


@tasks_bp.patch("/<int:task_id>")
@auth_required
def update_task(task_id):
    data, response = json_body()
    if response:
        return response
    allowed = {
        "title", "description", "status", "priority", "due_date", "category_id", "assignee_id"
    }
    if not data or any(key not in allowed for key in data):
        return error("no valid task fields supplied")
    message = validate_task(data, partial=True)
    if message:
        return error(message)
    db = get_db()
    exists = db.execute(
        "SELECT id FROM tasks WHERE id = ? AND creator_id = ?", (task_id, g.user["id"])
    ).fetchone()
    if exists is None:
        return error("task not found", 404)
    if "category_id" in data and not validate_reference(
        db, "categories", data["category_id"], g.user["id"]
    ):
        return error("category not found", 404)
    if "assignee_id" in data and not validate_reference(db, "users", data["assignee_id"]):
        return error("assignee not found", 404)
    if "title" in data:
        data["title"] = data["title"].strip()
    assignments = ", ".join(f"{field} = ?" for field in data)
    try:
        db.execute(
            f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (*data.values(), task_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return error("invalid task data")
    row = db.execute(TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()
    return jsonify(serialize_task(row))


@tasks_bp.delete("/<int:task_id>")
@auth_required
def delete_task(task_id):
    db = get_db()
    cursor = db.execute(
        "DELETE FROM tasks WHERE id = ? AND creator_id = ?", (task_id, g.user["id"])
    )
    db.commit()
    if cursor.rowcount == 0:
        return error("task not found", 404)
    return "", 204
