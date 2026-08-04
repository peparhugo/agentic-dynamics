from flask import Blueprint, request, jsonify, g, current_app

from app.database import get_db
from app.auth import login_required
from app.utils import (
    validate_required_fields,
    validate_status,
    validate_priority,
    validate_non_empty_string,
    build_pagination_meta,
    parse_pagination_args,
)

tasks_bp = Blueprint("tasks", __name__)

VALID_SORT_FIELDS = {"created_at", "updated_at", "due_date", "priority", "status", "title"}


def _task_row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"],
        "category_id": row["category_id"],
        "assigned_to": row["assigned_to"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@tasks_bp.route("", methods=["GET"])
@login_required
def list_tasks():
    db = get_db()

    page, per_page = parse_pagination_args(
        request.args,
        current_app.config.get("MAX_PAGE_SIZE", 100),
        current_app.config.get("DEFAULT_PAGE_SIZE", 20),
    )

    conditions = ["tasks.created_by = ?"]
    params = [g.current_user_id]

    status = request.args.get("status")
    if status:
        ok, msg = validate_status(status)
        if ok:
            conditions.append("tasks.status = ?")
            params.append(status)

    priority = request.args.get("priority")
    if priority:
        ok, msg = validate_priority(priority)
        if ok:
            conditions.append("tasks.priority = ?")
            params.append(priority)

    category_id = request.args.get("category_id")
    if category_id:
        try:
            conditions.append("tasks.category_id = ?")
            params.append(int(category_id))
        except (ValueError, TypeError):
            pass

    assigned_to = request.args.get("assigned_to")
    if assigned_to:
        try:
            conditions.append("tasks.assigned_to = ?")
            params.append(int(assigned_to))
        except (ValueError, TypeError):
            pass

    search = request.args.get("q")
    if search and search.strip():
        conditions.append("(tasks.title LIKE ? OR tasks.description LIKE ?)")
        term = f"%{search.strip()}%"
        params.extend([term, term])

    sort_by = request.args.get("sort_by", "created_at")
    if sort_by not in VALID_SORT_FIELDS:
        sort_by = "created_at"
    sort_order = request.args.get("sort_order", "desc")
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    where_clause = " WHERE " + " AND ".join(conditions)

    count_row = db.execute(
        f"SELECT COUNT(*) FROM tasks {where_clause}", params
    ).fetchone()
    total = count_row[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM tasks {where_clause} ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    tasks = [_task_row_to_dict(r) for r in rows]

    return jsonify(
        {"tasks": tasks, "pagination": build_pagination_meta(page, per_page, total)}
    )


@tasks_bp.route("", methods=["POST"])
@login_required
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    ok, msg = validate_required_fields(data, ["title"])
    if not ok:
        return jsonify({"error": msg}), 400

    title = data["title"].strip()
    ok, msg = validate_non_empty_string(title, "title")
    if not ok:
        return jsonify({"error": msg}), 400

    description = data.get("description", "").strip()
    status = data.get("status", "pending")
    priority = data.get("priority", "medium")
    due_date = data.get("due_date")
    category_id = data.get("category_id")
    assigned_to = data.get("assigned_to")

    ok, msg = validate_status(status)
    if not ok:
        return jsonify({"error": msg}), 400

    ok, msg = validate_priority(priority)
    if not ok:
        return jsonify({"error": msg}), 400

    db = get_db()

    if category_id is not None:
        cat = db.execute(
            "SELECT id FROM categories WHERE id = ? AND created_by = ?",
            (category_id, g.current_user_id),
        ).fetchone()
        if not cat:
            return jsonify({"error": "Category not found"}), 404

    if assigned_to is not None:
        user = db.execute(
            "SELECT id FROM users WHERE id = ?", (assigned_to,)
        ).fetchone()
        if not user:
            return jsonify({"error": "Assigned user not found"}), 404

    cursor = db.execute(
        """INSERT INTO tasks (title, description, status, priority, due_date, category_id, assigned_to, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (title, description, status, priority, due_date, category_id, assigned_to, g.current_user_id),
    )
    db.commit()

    task = db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"task": _task_row_to_dict(task)}), 201


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@login_required
def get_task(task_id):
    db = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": _task_row_to_dict(task)})


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    db = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    fields = {}
    if "title" in data:
        ok, msg = validate_non_empty_string(data["title"].strip(), "title")
        if not ok:
            return jsonify({"error": msg}), 400
        fields["title"] = data["title"].strip()

    if "description" in data:
        fields["description"] = data["description"].strip()

    if "status" in data:
        ok, msg = validate_status(data["status"])
        if not ok:
            return jsonify({"error": msg}), 400
        fields["status"] = data["status"]

    if "priority" in data:
        ok, msg = validate_priority(data["priority"])
        if not ok:
            return jsonify({"error": msg}), 400
        fields["priority"] = data["priority"]

    if "due_date" in data:
        fields["due_date"] = data["due_date"]

    if "category_id" in data:
        if data["category_id"] is not None:
            cat = db.execute(
                "SELECT id FROM categories WHERE id = ? AND created_by = ?",
                (data["category_id"], g.current_user_id),
            ).fetchone()
            if not cat:
                return jsonify({"error": "Category not found"}), 404
        fields["category_id"] = data["category_id"]

    if "assigned_to" in data:
        if data["assigned_to"] is not None:
            user = db.execute(
                "SELECT id FROM users WHERE id = ?", (data["assigned_to"],)
            ).fetchone()
            if not user:
                return jsonify({"error": "Assigned user not found"}), 404
        fields["assigned_to"] = data["assigned_to"]

    if not fields:
        return jsonify({"error": "No valid fields to update"}), 400

    fields["updated_at"] = db.execute("SELECT datetime('now')").fetchone()[0]

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
    db.commit()

    updated = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify({"task": _task_row_to_dict(updated)})


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    db = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({"message": "Task deleted"}), 200


@tasks_bp.route("/<int:task_id>/assign", methods=["POST"])
@login_required
def assign_task(task_id):
    db = get_db()
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?",
        (task_id, g.current_user_id),
    ).fetchone()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    ok, msg = validate_required_fields(data, ["user_id"])
    if not ok:
        return jsonify({"error": msg}), 400

    user = db.execute(
        "SELECT id FROM users WHERE id = ?", (data["user_id"],)
    ).fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404

    db.execute(
        "UPDATE tasks SET assigned_to = ?, updated_at = datetime('now') WHERE id = ?",
        (data["user_id"], task_id),
    )
    db.commit()

    updated = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify({"task": _task_row_to_dict(updated)})
