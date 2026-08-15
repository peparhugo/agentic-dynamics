from datetime import date

from flask import Blueprint, g, jsonify, request

from .auth import error, login_required
from .db import get_db

tasks_bp = Blueprint("tasks", __name__)
STATUSES = {"pending", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high"}
FIELDS = {"title", "description", "status", "category", "priority", "due_date", "assignee_id"}


def serialize(task):
    return {key: task[key] for key in task.keys()}


def visible_task(task_id):
    return get_db().execute(
        """SELECT tasks.*, creator.username AS creator_username,
                  assignee.username AS assignee_username
           FROM tasks
           JOIN users creator ON creator.id = tasks.creator_id
           LEFT JOIN users assignee ON assignee.id = tasks.assignee_id
           WHERE tasks.id = ? AND (tasks.creator_id = ? OR tasks.assignee_id = ?)""",
        (task_id, g.user["id"], g.user["id"]),
    ).fetchone()


def validate(data, partial=False):
    if not isinstance(data, dict):
        return "JSON object required"
    unknown = set(data) - FIELDS
    if unknown:
        return f"unknown field: {sorted(unknown)[0]}"
    for field in ("title", "category"):
        if not partial or field in data:
            if not isinstance(data.get(field), str) or not data[field].strip():
                return f"{field} is required"
    if "description" in data and not isinstance(data["description"], str):
        return "description must be a string"
    if "status" in data and data["status"] not in STATUSES:
        return "invalid status"
    if "priority" in data and data["priority"] not in PRIORITIES:
        return "invalid priority"
    if "due_date" in data and data["due_date"] is not None:
        try:
            date.fromisoformat(data["due_date"])
        except (TypeError, ValueError):
            return "due_date must use YYYY-MM-DD"
    if "assignee_id" in data and data["assignee_id"] is not None:
        if isinstance(data["assignee_id"], bool) or not isinstance(data["assignee_id"], int):
            return "assignee_id must be an integer or null"
        if get_db().execute("SELECT 1 FROM users WHERE id = ?", (data["assignee_id"],)).fetchone() is None:
            return "assignee does not exist"
    return None


@tasks_bp.post("")
@login_required
def create_task():
    data = request.get_json(silent=True)
    validation_error = validate(data)
    if validation_error:
        return error(validation_error, 400)
    db = get_db()
    cursor = db.execute(
        """INSERT INTO tasks
           (title, description, status, category, priority, due_date, creator_id, assignee_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data["title"].strip(), data.get("description", ""),
            data.get("status", "pending"), data["category"].strip(),
            data.get("priority", "medium"), data.get("due_date"),
            g.user["id"], data.get("assignee_id"),
        ),
    )
    db.commit()
    return jsonify(serialize(visible_task(cursor.lastrowid))), 201


@tasks_bp.get("")
@login_required
def list_tasks():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return error("page and per_page must be integers", 400)
    if page < 1 or per_page < 1 or per_page > 100:
        return error("page must be positive and per_page must be between 1 and 100", 400)

    clauses = ["(tasks.creator_id = ? OR tasks.assignee_id = ?)"]
    params = [g.user["id"], g.user["id"]]
    for field, allowed in (("status", STATUSES), ("priority", PRIORITIES)):
        value = request.args.get(field)
        if value:
            if value not in allowed:
                return error(f"invalid {field}", 400)
            clauses.append(f"tasks.{field} = ?")
            params.append(value)
    category = request.args.get("category")
    if category:
        clauses.append("tasks.category = ? COLLATE NOCASE")
        params.append(category)
    search = request.args.get("search")
    if search:
        clauses.append("(tasks.title LIKE ? OR tasks.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(clauses)
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
    rows = db.execute(
        f"""SELECT tasks.*, creator.username AS creator_username,
                    assignee.username AS assignee_username
             FROM tasks JOIN users creator ON creator.id = tasks.creator_id
             LEFT JOIN users assignee ON assignee.id = tasks.assignee_id
             WHERE {where} ORDER BY tasks.id DESC LIMIT ? OFFSET ?""",
        (*params, per_page, (page - 1) * per_page),
    ).fetchall()
    return jsonify(items=[serialize(row) for row in rows], page=page, per_page=per_page, total=total)


@tasks_bp.get("/<int:task_id>")
@login_required
def get_task(task_id):
    task = visible_task(task_id)
    if task is None:
        return error("task not found", 404)
    return jsonify(serialize(task))


@tasks_bp.patch("/<int:task_id>")
@login_required
def update_task(task_id):
    task = visible_task(task_id)
    if task is None:
        return error("task not found", 404)
    data = request.get_json(silent=True)
    validation_error = validate(data, partial=True)
    if validation_error:
        return error(validation_error, 400)
    if not data:
        return error("at least one field is required", 400)
    if "assignee_id" in data and task["creator_id"] != g.user["id"]:
        return error("only the creator may reassign a task", 403)

    values = dict(data)
    for field in ("title", "category"):
        if field in values:
            values[field] = values[field].strip()
    assignments = ", ".join(f"{field} = ?" for field in values)
    db = get_db()
    db.execute(
        f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (*values.values(), task_id),
    )
    db.commit()
    return jsonify(serialize(visible_task(task_id)))


@tasks_bp.delete("/<int:task_id>")
@login_required
def delete_task(task_id):
    task = visible_task(task_id)
    if task is None:
        return error("task not found", 404)
    if task["creator_id"] != g.user["id"]:
        return error("only the creator may delete a task", 403)
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return "", 204
