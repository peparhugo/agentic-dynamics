from datetime import date

from flask import Blueprint, g, jsonify, request

from .auth import token_required
from .db import get_db
from .errors import ApiError
from .users import TASK_SELECT, VALID_PRIORITIES, VALID_STATUSES, _task_row_to_dict

bp = Blueprint("tasks", __name__)


def _validate_payload(payload, partial=False):
    allowed = {"title", "description", "status", "priority", "category_id", "due_date", "assigned_to"}
    for key in payload:
        if key not in allowed:
            raise ApiError(f"Unknown field: {key}", 400)

    errors = {}
    fields = {}

    title = payload.get("title")
    if title is not None:
        title = title.strip()
        if not title:
            errors["title"] = "title must not be empty"
        elif len(title) > 255:
            errors["title"] = "title must be at most 255 characters"
        fields["title"] = title

    if "description" in payload:
        description = payload.get("description") or ""
        if not isinstance(description, str):
            errors["description"] = "description must be a string"
        else:
            fields["description"] = description

    if "status" in payload:
        status = payload.get("status")
        if status not in VALID_STATUSES:
            errors["status"] = f"status must be one of {', '.join(VALID_STATUSES)}"
        else:
            fields["status"] = status

    if "priority" in payload:
        priority = payload.get("priority")
        if priority not in VALID_PRIORITIES:
            errors["priority"] = f"priority must be one of {', '.join(VALID_PRIORITIES)}"
        else:
            fields["priority"] = priority

    if "category_id" in payload:
        category_id = payload.get("category_id")
        if category_id is not None:
            try:
                category_id = int(category_id)
            except (TypeError, ValueError):
                errors["category_id"] = "category_id must be an integer"
                category_id = None
        if category_id is not None:
            db = get_db()
            row = db.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
            if row is None:
                errors["category_id"] = "category does not exist"
        fields["category_id"] = category_id

    if "due_date" in payload:
        raw = payload.get("due_date")
        if raw is None:
            fields["due_date"] = None
        else:
            try:
                fields["due_date"] = date.fromisoformat(raw).isoformat()
            except (TypeError, ValueError):
                errors["due_date"] = "due_date must be a valid ISO date (YYYY-MM-DD)"

    if "assigned_to" in payload:
        assigned_to = payload.get("assigned_to")
        if assigned_to is not None:
            try:
                assigned_to = int(assigned_to)
            except (TypeError, ValueError):
                errors["assigned_to"] = "assigned_to must be an integer"
                assigned_to = None
        if assigned_to is not None:
            row = get_db().execute("SELECT id FROM users WHERE id = ?", (assigned_to,)).fetchone()
            if row is None:
                errors["assigned_to"] = "assigned user does not exist"
        fields["assigned_to"] = assigned_to

    if errors:
        raise ApiError("Validation failed", 422, errors=errors)
    return fields


def _build_filters(args):
    clauses = []
    params = []

    status = args.get("status")
    if status:
        if status not in VALID_STATUSES:
            raise ApiError(f"status filter must be one of {', '.join(VALID_STATUSES)}", 400)
        clauses.append("t.status = ?")
        params.append(status)

    priority = args.get("priority")
    if priority:
        if priority not in VALID_PRIORITIES:
            raise ApiError(f"priority filter must be one of {', '.join(VALID_PRIORITIES)}", 400)
        clauses.append("t.priority = ?")
        params.append(priority)

    category = args.get("category_id")
    if category:
        try:
            clauses.append("t.category_id = ?")
            params.append(int(category))
        except (TypeError, ValueError):
            raise ApiError("category_id must be an integer", 400)

    category_name = args.get("category")
    if category_name:
        clauses.append("c.name = ?")
        params.append(category_name)

    assigned_to = args.get("assigned_to")
    if assigned_to:
        try:
            clauses.append("t.assigned_to = ?")
            params.append(int(assigned_to))
        except (TypeError, ValueError):
            raise ApiError("assigned_to must be an integer", 400)

    created_by = args.get("created_by")
    if created_by:
        try:
            clauses.append("t.created_by = ?")
            params.append(int(created_by))
        except (TypeError, ValueError):
            raise ApiError("created_by must be an integer", 400)

    query = args.get("q") or args.get("search")
    if query:
        clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])

    return clauses, params


def _paginate_args(args):
    try:
        page = max(int(args.get("page", 1)), 1)
    except (TypeError, ValueError):
        raise ApiError("page must be an integer", 400)
    try:
        per_page = int(args.get("per_page", 10))
    except (TypeError, ValueError):
        raise ApiError("per_page must be an integer", 400)
    if per_page < 1:
        raise ApiError("per_page must be at least 1", 400)
    per_page = min(per_page, 100)
    return page, per_page


@bp.get("/tasks")
@token_required
def list_tasks():
    args = request.args
    clauses, params = _build_filters(args)
    page, per_page = _paginate_args(args)

    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    sort_map = {
        "created_at": "t.created_at",
        "due_date": "t.due_date",
        "priority": "CASE t.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END",
        "title": "t.title",
    }
    sort = args.get("sort", "created_at")
    if sort not in sort_map:
        raise ApiError(f"sort must be one of {', '.join(sort_map)}", 400)
    order = args.get("order", "desc")
    if order not in ("asc", "desc"):
        raise ApiError("order must be 'asc' or 'desc'", 400)

    db = get_db()
    total = db.execute(
        f"SELECT COUNT(*) AS n FROM tasks t LEFT JOIN categories c ON c.id = t.category_id {where}",
        params,
    ).fetchone()["n"]

    rows = db.execute(
        f"{TASK_SELECT} {where} ORDER BY {sort_map[sort]} {order.upper()}, t.id {order.upper()} "
        "LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()

    return jsonify(
        {
            "items": [_task_row_to_dict(r) for r in rows],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page,
            },
        }
    )


@bp.post("/tasks")
@token_required
def create_task():
    payload = request.get_json(silent=True)
    if payload is None:
        raise ApiError("Request body must be valid JSON", 400)
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object", 400)

    fields = _validate_payload(payload, partial=False)
    if "title" not in fields:
        raise ApiError("title is required", 422, errors={"title": "title is required"})

    db = get_db()
    cur = db.execute(
        """
        INSERT INTO tasks (title, description, status, priority, category_id, due_date,
                           created_by, assigned_to)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fields.get("title"),
            fields.get("description", ""),
            fields.get("status", "pending"),
            fields.get("priority", "medium"),
            fields.get("category_id"),
            fields.get("due_date"),
            g.current_user["id"],
            fields.get("assigned_to"),
        ),
    )
    db.commit()
    row = db.execute(f"{TASK_SELECT} WHERE t.id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(_task_row_to_dict(row)), 201


@bp.get("/tasks/<int:task_id>")
@token_required
def get_task(task_id):
    row = get_db().execute(f"{TASK_SELECT} WHERE t.id = ?", (task_id,)).fetchone()
    if row is None:
        raise ApiError("Task not found", 404)
    return jsonify(_task_row_to_dict(row))


@bp.put("/tasks/<int:task_id>")
@bp.patch("/tasks/<int:task_id>")
@token_required
def update_task(task_id):
    db = get_db()
    existing = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if existing is None:
        raise ApiError("Task not found", 404)

    payload = request.get_json(silent=True)
    if payload is None:
        raise ApiError("Request body must be valid JSON", 400)
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object", 400)

    fields = _validate_payload(payload, partial=True)

    if not fields:
        raise ApiError("No valid fields to update", 400)

    current = {
        "title": existing["title"],
        "description": existing["description"],
        "status": existing["status"],
        "priority": existing["priority"],
        "category_id": existing["category_id"],
        "due_date": existing["due_date"],
        "assigned_to": existing["assigned_to"],
    }
    current.update(fields)

    db.execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, status = ?, priority = ?, category_id = ?,
            due_date = ?, assigned_to = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (
            current["title"],
            current["description"],
            current["status"],
            current["priority"],
            current["category_id"],
            current["due_date"],
            current["assigned_to"],
            task_id,
        ),
    )
    db.commit()
    row = db.execute(f"{TASK_SELECT} WHERE t.id = ?", (task_id,)).fetchone()
    return jsonify(_task_row_to_dict(row))


@bp.delete("/tasks/<int:task_id>")
@token_required
def delete_task(task_id):
    db = get_db()
    existing = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if existing is None:
        raise ApiError("Task not found", 404)
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return "", 204
