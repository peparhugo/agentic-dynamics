from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.db import (
    PRIORITY_RANK,
    VALID_PRIORITIES,
    VALID_STATUSES,
    get_db,
)

bp = Blueprint("tasks", __name__, url_prefix="/tasks")


def _serialize_task(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "category_id": row["category_id"],
        "category_name": row["category_name"],
        "due_date": row["due_date"],
        "assignee_id": row["assignee_id"],
        "assignee_username": row["assignee_username"],
        "creator_id": row["creator_id"],
        "creator_username": row["creator_username"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _task_select():
    return (
        "SELECT t.*, "
        "c.name AS category_name, "
        "a.username AS assignee_username, "
        "u.username AS creator_username "
        "FROM tasks t "
        "LEFT JOIN categories c ON c.id = t.category_id "
        "LEFT JOIN users a ON a.id = t.assignee_id "
        "LEFT JOIN users u ON u.id = t.creator_id "
    )


def _find_task(task_id):
    row = get_db().execute(_task_select() + " WHERE t.id = ?", (task_id,)).fetchone()
    return row


def _user_exists(user_id):
    return (
        get_db().execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        is not None
    )


def _category_exists(category_id):
    return (
        get_db().execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
        is not None
    )


def _parse_date(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return "invalid"


def _validate_task_payload(data, partial=False):
    errors = {}
    title = data.get("title")
    if title is not None:
        title = str(title).strip()
        if not title:
            errors["title"] = "title is required"
    if not partial and title is None:
        errors["title"] = "title is required"

    status = data.get("status")
    if status is not None and status not in VALID_STATUSES:
        errors["status"] = f"status must be one of {sorted(VALID_STATUSES)}"

    priority = data.get("priority")
    if priority is not None and priority not in VALID_PRIORITIES:
        errors["priority"] = f"priority must be one of {sorted(VALID_PRIORITIES)}"

    category_id = data.get("category_id")
    if category_id is not None and category_id != "":
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            errors["category_id"] = "category_id must be an integer"
        else:
            if category_id is not None and not _category_exists(category_id):
                errors["category_id"] = "category not found"

    assignee_id = data.get("assignee_id")
    if assignee_id is not None and assignee_id != "":
        try:
            assignee_id = int(assignee_id)
        except (TypeError, ValueError):
            errors["assignee_id"] = "assignee_id must be an integer"
        else:
            if not _user_exists(assignee_id):
                errors["assignee_id"] = "assignee user not found"

    due_date = data.get("due_date")
    if due_date is not None and due_date != "":
        parsed = _parse_date(due_date)
        if parsed == "invalid":
            errors["due_date"] = "due_date must be a valid ISO date (YYYY-MM-DD)"

    return errors


def _can_modify(task_row, user):
    if user is None:
        return False
    if user["is_admin"]:
        return True
    return str(task_row["creator_id"]) == str(user["id"]) or str(
        task_row["assignee_id"]
    ) == str(user["id"])


def _extract_update(data, partial=False):
    update = {}
    fields = ("title", "description", "status", "priority", "due_date")
    for field in fields:
        if field in data:
            value = data[field]
            if field == "title":
                value = str(value).strip()
            elif field == "due_date":
                value = _parse_date(value)
            update[field] = value if value is not None else None
    for field in ("category_id", "assignee_id"):
        if field in data:
            value = data[field]
            if value in (None, ""):
                update[field] = None
            else:
                update[field] = int(value)
    return update


@bp.get("")
@jwt_required()
def list_tasks():
    args = request.args
    db = get_db()
    where = []
    params = []

    status = args.get("status")
    if status:
        if status not in VALID_STATUSES:
            return jsonify(
                {"error": f"status must be one of {sorted(VALID_STATUSES)}"}
            ), 400
        where.append("t.status = ?")
        params.append(status)

    priority = args.get("priority")
    if priority:
        if priority not in VALID_PRIORITIES:
            return jsonify(
                {"error": f"priority must be one of {sorted(VALID_PRIORITIES)}"}
            ), 400
        where.append("t.priority = ?")
        params.append(priority)

    category_id = args.get("category_id")
    if category_id:
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            return jsonify({"error": "category_id must be an integer"}), 400
        if not _category_exists(category_id):
            return jsonify({"error": "category not found"}), 404
        where.append("t.category_id = ?")
        params.append(category_id)

    assignee_id = args.get("assignee_id")
    if assignee_id:
        try:
            assignee_id = int(assignee_id)
        except (TypeError, ValueError):
            return jsonify({"error": "assignee_id must be an integer"}), 400
        where.append("t.assignee_id = ?")
        params.append(assignee_id)

    search = args.get("search")
    if search:
        like = f"%{search}%"
        where.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([like, like])

    sort_by = args.get("sort_by", "created_at")
    allowed_sort = {
        "created_at": "t.created_at",
        "updated_at": "t.updated_at",
        "due_date": "t.due_date",
        "priority": "t.priority",
        "title": "t.title COLLATE NOCASE",
    }
    if sort_by not in allowed_sort:
        return jsonify({"error": f"sort_by must be one of {sorted(allowed_sort)}"}), 400

    sort_order = args.get("sort_order", "desc").lower()
    if sort_order not in ("asc", "desc"):
        return jsonify({"error": "sort_order must be 'asc' or 'desc'"}), 400

    try:
        page = int(args.get("page", 1))
        per_page = int(args.get("per_page", 20))
    except (TypeError, ValueError):
        return jsonify({"error": "page and per_page must be integers"}), 400

    if page < 1:
        return jsonify({"error": "page must be at least 1"}), 400
    if per_page < 1 or per_page > 100:
        return jsonify({"error": "per_page must be between 1 and 100"}), 400

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.execute(
        f"SELECT COUNT(*) AS n FROM tasks t{where_sql}", params
    ).fetchone()["n"]

    order_column = allowed_sort[sort_by]
    if sort_by == "priority":
        order_column = "CASE t.priority WHEN 'low' THEN 0 WHEN 'medium' THEN 1 WHEN 'high' THEN 2 END"

    order_sql = f"{order_column} {sort_order}, t.id {sort_order}"
    offset = (page - 1) * per_page

    rows = db.execute(
        f"{_task_select()}{where_sql} ORDER BY {order_sql} "
        f"LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    pages = (total + per_page - 1) // per_page if total else 0

    return (
        jsonify(
            {
                "items": [_serialize_task(r) for r in rows],
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": pages,
            }
        ),
        200,
    )


@bp.get("/stats")
@jwt_required()
def task_stats():
    db = get_db()
    by_status = {
        row["status"]: row["n"]
        for row in db.execute(
            "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
        ).fetchall()
    }
    by_priority = {
        row["priority"]: row["n"]
        for row in db.execute(
            "SELECT priority, COUNT(*) AS n FROM tasks GROUP BY priority"
        ).fetchall()
    }
    return (
        jsonify(
            {
                "total": sum(by_status.values()),
                "by_status": by_status,
                "by_priority": by_priority,
            }
        ),
        200,
    )


@bp.post("")
@jwt_required()
def create_task():
    data = request.get_json(silent=True) or {}
    errors = _validate_task_payload(data)
    if errors:
        return jsonify({"error": "validation failed", "details": errors}), 400

    creator = get_jwt_identity()
    update = _extract_update(data)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO tasks (title, description, status, priority, category_id, "
        "due_date, assignee_id, creator_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            update.get("title") or data.get("title", "").strip(),
            (data.get("description") or "").strip(),
            update.get("status") or "pending",
            update.get("priority") or "medium",
            update.get("category_id"),
            update.get("due_date"),
            update.get("assignee_id"),
            creator,
        ),
    )
    db.commit()
    return jsonify(_serialize_task(_find_task(cursor.lastrowid))), 201


@bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id):
    row = _find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(_serialize_task(row)), 200


@bp.put("/<int:task_id>")
@jwt_required()
def update_task(task_id):
    user_id = get_jwt_identity()
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    row = _find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    if not _can_modify(row, user):
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if "title" not in data:
        return jsonify({"error": "title is required for full update"}), 400

    errors = _validate_task_payload(data)
    if errors:
        return jsonify({"error": "validation failed", "details": errors}), 400

    update = _extract_update(data)
    db = get_db()
    db.execute(
        "UPDATE tasks SET title = ?, description = ?, status = ?, priority = ?, "
        "category_id = ?, due_date = ?, assignee_id = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (
            update["title"],
            (data.get("description") or "").strip(),
            update.get("status") or "pending",
            update.get("priority") or "medium",
            update.get("category_id"),
            update.get("due_date"),
            update.get("assignee_id"),
            task_id,
        ),
    )
    db.commit()
    return jsonify(_serialize_task(_find_task(task_id))), 200


@bp.patch("/<int:task_id>")
@jwt_required()
def patch_task(task_id):
    user_id = get_jwt_identity()
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    row = _find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    if not _can_modify(row, user):
        return jsonify({"error": "forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "no fields to update"}), 400

    errors = _validate_task_payload(data, partial=True)
    if errors:
        return jsonify({"error": "validation failed", "details": errors}), 400

    update = _extract_update(data, partial=True)
    db = get_db()
    sets = []
    params = []
    for field in ("title", "description", "status", "priority", "category_id",
                  "due_date", "assignee_id"):
        if field in update:
            sets.append(f"{field} = ?")
            params.append(update[field])
    if not sets:
        return jsonify({"error": "no valid fields to update"}), 400
    sets.append("updated_at = datetime('now')")
    params.append(task_id)
    db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
    db.commit()
    return jsonify(_serialize_task(_find_task(task_id))), 200


@bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    user_id = get_jwt_identity()
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    row = _find_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    if not _can_modify(row, user):
        return jsonify({"error": "forbidden"}), 403

    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({"message": "task deleted"}), 200
