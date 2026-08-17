from datetime import date

from flask import Blueprint, current_app, g, jsonify, request

from .auth import login_required
from .db import get_db


bp = Blueprint("tasks", __name__, url_prefix="/tasks")
STATUSES = {"todo", "in_progress", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}


TASK_SELECT = """
SELECT t.*, c.name AS category_name, a.name AS assignee_name,
       a.email AS assignee_email, o.name AS owner_name
FROM tasks t
LEFT JOIN categories c ON c.id = t.category_id
LEFT JOIN users a ON a.id = t.assignee_id
JOIN users o ON o.id = t.owner_id
"""


def serialize_task(row):
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
        "owner": {"id": row["owner_id"], "name": row["owner_name"]},
        "assignee": (
            {
                "id": row["assignee_id"],
                "name": row["assignee_name"],
                "email": row["assignee_email"],
            }
            if row["assignee_id"] is not None
            else None
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def accessible_task(database, task_id):
    return database.execute(
        TASK_SELECT + " WHERE t.id = ? AND (t.owner_id = ? OR t.assignee_id = ?)",
        (task_id, g.user["id"], g.user["id"]),
    ).fetchone()


def validate_fields(body, creating=False, owner=False):
    if not isinstance(body, dict):
        return None, "JSON object required"
    allowed = {"title", "description", "status", "priority", "due_date", "category_id"}
    if owner:
        allowed.add("assignee_id")
    unknown = set(body) - allowed
    if unknown:
        return None, f"Unknown fields: {', '.join(sorted(unknown))}"
    values = {}
    if creating or "title" in body:
        title = str(body.get("title", "")).strip()
        if not title or len(title) > 200:
            return None, "Title is required and must be at most 200 characters"
        values["title"] = title
    if "description" in body:
        if body["description"] is not None and not isinstance(body["description"], str):
            return None, "Description must be a string or null"
        values["description"] = body["description"]
    for field, choices in (("status", STATUSES), ("priority", PRIORITIES)):
        if field in body:
            if body[field] not in choices:
                return None, f"{field.capitalize()} must be one of: {', '.join(sorted(choices))}"
            values[field] = body[field]
    if "due_date" in body:
        if body["due_date"] is not None:
            try:
                date.fromisoformat(body["due_date"])
            except (TypeError, ValueError):
                return None, "Due date must use YYYY-MM-DD format or be null"
        values["due_date"] = body["due_date"]
    for field in ("category_id", "assignee_id"):
        if field in body:
            if body[field] is not None and (not isinstance(body[field], int) or isinstance(body[field], bool)):
                return None, f"{field} must be an integer or null"
            values[field] = body[field]
    return values, None


def validate_relations(database, values):
    category_id = values.get("category_id")
    if category_id is not None and database.execute(
        "SELECT 1 FROM categories WHERE id = ? AND user_id = ?",
        (category_id, g.user["id"]),
    ).fetchone() is None:
        return "Category not found"
    assignee_id = values.get("assignee_id")
    if assignee_id is not None and database.execute(
        "SELECT 1 FROM users WHERE id = ?", (assignee_id,)
    ).fetchone() is None:
        return "Assignee not found"
    return None


@bp.post("")
@login_required
def create_task():
    values, error = validate_fields(request.get_json(silent=True), creating=True, owner=True)
    if error:
        return jsonify(error="validation_error", message=error), 400
    database = get_db()
    relation_error = validate_relations(database, values)
    if relation_error:
        return jsonify(error="validation_error", message=relation_error), 400
    values.setdefault("description", None)
    values.setdefault("status", "todo")
    values.setdefault("priority", "medium")
    values.setdefault("due_date", None)
    values.setdefault("category_id", None)
    values.setdefault("assignee_id", None)
    cursor = database.execute(
        """INSERT INTO tasks
           (owner_id, assignee_id, category_id, title, description, status, priority, due_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            g.user["id"], values["assignee_id"], values["category_id"], values["title"],
            values["description"], values["status"], values["priority"], values["due_date"],
        ),
    )
    database.commit()
    row = database.execute(TASK_SELECT + " WHERE t.id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(task=serialize_task(row)), 201


@bp.get("")
@login_required
def list_tasks():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        return jsonify(error="validation_error", message="page and per_page must be integers"), 400
    if page < 1 or per_page < 1 or per_page > current_app.config["MAX_PAGE_SIZE"]:
        return jsonify(error="validation_error", message=f"page must be positive and per_page must be 1-{current_app.config['MAX_PAGE_SIZE']}"), 400

    clauses = ["(t.owner_id = ? OR t.assignee_id = ?)"]
    params = [g.user["id"], g.user["id"]]
    for field, choices in (("status", STATUSES), ("priority", PRIORITIES)):
        value = request.args.get(field)
        if value:
            if value not in choices:
                return jsonify(error="validation_error", message=f"Invalid {field}"), 400
            clauses.append(f"t.{field} = ?")
            params.append(value)
    category = request.args.get("category")
    if category:
        clauses.append("(c.name = ? OR CAST(c.id AS TEXT) = ?)")
        params.extend([category, category])
    search = request.args.get("search", "").strip()
    if search:
        clauses.append("(t.title LIKE ? COLLATE NOCASE OR t.description LIKE ? COLLATE NOCASE)")
        params.extend([f"%{search}%", f"%{search}%"])
    assignee_id = request.args.get("assignee_id")
    if assignee_id:
        try:
            assignee_id = int(assignee_id)
        except ValueError:
            return jsonify(error="validation_error", message="assignee_id must be an integer"), 400
        clauses.append("t.assignee_id = ?")
        params.append(assignee_id)

    where = " WHERE " + " AND ".join(clauses)
    database = get_db()
    total = database.execute(
        "SELECT COUNT(*) AS count FROM tasks t LEFT JOIN categories c ON c.id = t.category_id" + where,
        params,
    ).fetchone()["count"]
    rows = database.execute(
        TASK_SELECT + where + " ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()
    return jsonify(
        tasks=[serialize_task(row) for row in rows],
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    )


@bp.get("/<int:task_id>")
@login_required
def get_task(task_id):
    row = accessible_task(get_db(), task_id)
    if row is None:
        return jsonify(error="not_found", message="Task not found"), 404
    return jsonify(task=serialize_task(row))


@bp.patch("/<int:task_id>")
@login_required
def update_task(task_id):
    database = get_db()
    row = accessible_task(database, task_id)
    if row is None:
        return jsonify(error="not_found", message="Task not found"), 404
    is_owner = row["owner_id"] == g.user["id"]
    values, error = validate_fields(request.get_json(silent=True), owner=is_owner)
    if error:
        return jsonify(error="validation_error", message=error), 400
    if not values:
        return jsonify(error="validation_error", message="At least one field is required"), 400
    relation_error = validate_relations(database, values)
    if relation_error:
        return jsonify(error="validation_error", message=relation_error), 400
    assignments = ", ".join(f"{field} = ?" for field in values)
    database.execute(
        f"UPDATE tasks SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [*values.values(), task_id],
    )
    database.commit()
    updated = database.execute(TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()
    return jsonify(task=serialize_task(updated))


@bp.delete("/<int:task_id>")
@login_required
def delete_task(task_id):
    database = get_db()
    cursor = database.execute(
        "DELETE FROM tasks WHERE id = ? AND owner_id = ?", (task_id, g.user["id"])
    )
    database.commit()
    if cursor.rowcount == 0:
        return jsonify(error="not_found", message="Task not found"), 404
    return "", 204
