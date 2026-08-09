from flask import Blueprint, request, jsonify, current_app
from app import get_db, now_utc
from app.auth import user_required, current_user_id

task_bp = Blueprint("tasks", __name__)

VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


def _task_row_to_dict(row):
    t = dict(row)
    return {
        "id": t["id"],
        "title": t["title"],
        "description": t["description"],
        "status": t["status"],
        "priority": t["priority"],
        "category": t["category"],
        "due_date": t["due_date"],
        "assigned_to": t["assigned_to"],
        "created_by": t["created_by"],
        "created_at": t["created_at"],
        "updated_at": t["updated_at"],
    }


@task_bp.route("", methods=["POST"])
@user_required
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 422

    status = data.get("status", "pending")
    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}), 422

    priority = data.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"}), 422

    description = data.get("description") or ""
    category = data.get("category") or "general"
    due_date = data.get("due_date") or None
    assigned_to = data.get("assigned_to")
    created_by = current_user_id()
    now = now_utc()

    if assigned_to is not None:
        from app.models import User
        if not User.find_by_id(assigned_to):
            return jsonify({"error": "Assigned user not found"}), 422
        assigned_to = int(assigned_to)

    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO tasks (title, description, status, priority, category, due_date,
               assigned_to, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, status, priority, category, due_date, assigned_to, created_by, now, now),
        )
        db.commit()
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify({"task": _task_row_to_dict(row)}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500


@task_bp.route("", methods=["GET"])
@user_required
def list_tasks():
    user_id = current_user_id()
    db = get_db()

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", current_app.config["PAGE_SIZE_DEFAULT"], type=int)
    per_page = min(per_page, current_app.config["PAGE_SIZE_MAX"])

    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")
    category_filter = request.args.get("category")
    search = request.args.get("search")
    assigned_to = request.args.get("assigned_to", type=int)
    created_by = request.args.get("created_by", type=int)
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")

    allowed_sort_columns = {"id", "title", "status", "priority", "category", "due_date", "created_at", "updated_at"}
    if sort_by not in allowed_sort_columns:
        sort_by = "created_at"
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    conditions = []
    params = []

    conditions.append("(assigned_to = ? OR created_by = ? OR assigned_to IS NULL)")
    params.extend([user_id, user_id])

    if status_filter:
        if status_filter not in VALID_STATUSES:
            return jsonify({"error": f"Invalid status filter. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}), 422
        conditions.append("status = ?")
        params.append(status_filter)

    if priority_filter:
        if priority_filter not in VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority filter. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"}), 422
        conditions.append("priority = ?")
        params.append(priority_filter)

    if category_filter:
        conditions.append("category = ?")
        params.append(category_filter)

    if search:
        conditions.append("(title LIKE ? OR description LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])

    if assigned_to is not None:
        conditions.append("assigned_to = ?")
        params.append(assigned_to)

    if created_by is not None:
        conditions.append("created_by = ?")
        params.append(created_by)

    where_clause = " AND ".join(conditions)

    count_cursor = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where_clause}", params)
    total = count_cursor.fetchone()[0]

    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM tasks WHERE {where_clause} ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    tasks = [_task_row_to_dict(r) for r in rows]

    return jsonify({
        "tasks": tasks,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page if total > 0 else 0,
        },
    }), 200


@task_bp.route("/<int:task_id>", methods=["GET"])
@user_required
def get_task(task_id):
    user_id = current_user_id()
    db = get_db()
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND (assigned_to = ? OR created_by = ?)",
        (task_id, user_id, user_id),
    ).fetchone()
    if not row:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": _task_row_to_dict(row)}), 200


@task_bp.route("/<int:task_id>", methods=["PUT"])
@user_required
def update_task(task_id):
    user_id = current_user_id()
    db = get_db()
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND (assigned_to = ? OR created_by = ?)",
        (task_id, user_id, user_id),
    ).fetchone()
    if not row:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    t = dict(row)
    title = (data.get("title") or t["title"]).strip()
    description = data.get("description") if "description" in data else t["description"]
    status = data.get("status", t["status"])
    priority = data.get("priority", t["priority"])
    category = data.get("category", t["category"])
    due_date = data.get("due_date") if "due_date" in data else t["due_date"]
    assigned_to = data.get("assigned_to") if "assigned_to" in data else t["assigned_to"]

    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}"}), 422
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"}), 422

    if assigned_to is not None:
        from app.models import User
        if not User.find_by_id(assigned_to):
            return jsonify({"error": "Assigned user not found"}), 422
        assigned_to = int(assigned_to)

    now = now_utc()
    try:
        db.execute(
            """UPDATE tasks SET title=?, description=?, status=?, priority=?, category=?,
               due_date=?, assigned_to=?, updated_at=?
               WHERE id=?""",
            (title, description, status, priority, category, due_date, assigned_to, now, task_id),
        )
        db.commit()
        updated = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return jsonify({"task": _task_row_to_dict(updated)}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500


@task_bp.route("/<int:task_id>", methods=["DELETE"])
@user_required
def delete_task(task_id):
    user_id = current_user_id()
    db = get_db()
    row = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?",
        (task_id, user_id),
    ).fetchone()
    if not row:
        return jsonify({"error": "Task not found or you are not the creator"}), 404
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({"message": "Task deleted"}), 200
