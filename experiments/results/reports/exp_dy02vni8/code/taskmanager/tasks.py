from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from .db import get_db
from .security import parse_date, validate_status
from .utils import TASK_SELECT, resolve_category, resolve_priority, task_to_dict

bp = Blueprint("tasks", __name__, url_prefix="/tasks")

SORT_FIELDS = {
    "created_at": "t.created_at",
    "due_date": "t.due_date",
    "title": "t.title",
    "priority": "p.level",
}


def _current_user_id():
    return int(get_jwt_identity())


def _parse_task_payload(data, partial=False):
    db = get_db()
    fields = {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            raise ValueError("title is required and cannot be empty")
        fields["title"] = title

    if "description" in data:
        fields["description"] = str(data.get("description") or "")

    if "status" in data:
        fields["status"] = validate_status(data.get("status"))

    if "priority" in data or "priority_id" in data:
        value = data.get("priority", data.get("priority_id"))
        priority = resolve_priority(db, value)
        fields["priority_id"] = priority["id"] if priority is not None else None

    if "category" in data or "category_id" in data:
        value = data.get("category", data.get("category_id"))
        category = resolve_category(db, value)
        fields["category_id"] = category["id"] if category is not None else None

    if "due_date" in data:
        parsed = parse_date(data.get("due_date"))
        fields["due_date"] = parsed

    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is None:
            fields["assignee_id"] = None
        else:
            user = db.execute(
                "SELECT id FROM users WHERE id = ?", (int(assignee_id),)
            ).fetchone()
            if user is None:
                raise ValueError(f"unknown assignee_id '{assignee_id}'")
            fields["assignee_id"] = user["id"]

    if not partial and "title" not in fields:
        raise ValueError("title is required")

    return fields


@bp.post("")
@jwt_required()
def create_task():
    data = request.get_json(silent=True) or {}
    try:
        fields = _parse_task_payload(data)
    except ValueError as exc:
        return {"error": str(exc)}, 400

    fields["creator_id"] = _current_user_id()
    db = get_db()
    columns = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    cur = db.execute(
        f"INSERT INTO tasks ({columns}) VALUES ({placeholders})", tuple(fields.values())
    )
    db.commit()
    row = db.execute(TASK_SELECT + " WHERE t.id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(task_to_dict(row)), 201


@bp.get("")
@jwt_required()
def list_tasks():
    db = get_db()
    args = request.args
    clauses = []
    params = []

    status = args.get("status")
    if status:
        try:
            validate_status(status)
        except ValueError as exc:
            return {"error": str(exc)}, 400
        clauses.append("t.status = ?")
        params.append(status)

    priority_ref = args.get("priority") or args.get("priority_id")
    if priority_ref:
        priority = resolve_priority(db, priority_ref)
        clauses.append("t.priority_id = ?")
        params.append(priority["id"])

    category_ref = args.get("category") or args.get("category_id")
    if category_ref:
        category = resolve_category(db, category_ref)
        clauses.append("t.category_id = ?")
        params.append(category["id"])

    assignee = args.get("assignee_id")
    if assignee:
        clauses.append("t.assignee_id = ?")
        params.append(int(assignee))

    creator = args.get("creator_id")
    if creator:
        clauses.append("t.creator_id = ?")
        params.append(int(creator))

    unassigned = args.get("unassigned")
    if unassigned in ("1", "true", "True"):
        clauses.append("t.assignee_id IS NULL")

    q = args.get("q")
    if q:
        clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
        pattern = f"%{q}%"
        params.extend([pattern, pattern])

    due_before = args.get("due_before")
    if due_before:
        clauses.append("t.due_date <= ?")
        params.append(parse_date(due_before, "due_before"))

    due_after = args.get("due_after")
    if due_after:
        clauses.append("t.due_date >= ?")
        params.append(parse_date(due_after, "due_after"))

    where = " WHERE " + " AND ".join(clauses) if clauses else ""

    total = db.execute(
        "SELECT COUNT(*) AS c FROM tasks t" + where,
        params,
    ).fetchone()["c"]

    try:
        page = max(int(args.get("page", 1)), 1)
        per_page = min(max(int(args.get("per_page", 20)), 1), 100)
    except ValueError:
        return {"error": "page and per_page must be integers"}, 400

    sort = args.get("sort", "created_at")
    direction = args.get("sort_dir", "asc").lower()
    sort_column = SORT_FIELDS.get(sort)
    if sort_column is None:
        return {"error": f"invalid sort field; must be one of {', '.join(SORT_FIELDS)}"}, 400
    if direction not in ("asc", "desc"):
        return {"error": "sort_dir must be 'asc' or 'desc'"}, 400

    nulls_last = " NULLS LAST" if sort == "due_date" else ""
    order_by = f" ORDER BY {sort_column} {direction.upper()}{nulls_last}, t.id ASC"
    offset = (page - 1) * per_page
    rows = db.execute(
        TASK_SELECT + where + order_by + " LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    pages = (total + per_page - 1) // per_page
    return jsonify(
        {
            "items": [task_to_dict(r) for r in rows],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
            },
        }
    )


def _fetch_task(task_id):
    db = get_db()
    return db.execute(TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()


@bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id):
    row = _fetch_task(task_id)
    if row is None:
        return {"error": "task not found"}, 404
    return jsonify(task_to_dict(row))


def _can_edit(row, user_id):
    return row["creator_id"] == user_id or row["assignee_id"] == user_id


@bp.put("/<int:task_id>")
@jwt_required()
def update_task(task_id):
    row = _fetch_task(task_id)
    if row is None:
        return {"error": "task not found"}, 404
    user_id = _current_user_id()
    if not _can_edit(row, user_id):
        return {"error": "forbidden: only the creator or assignee may update this task"}, 403

    data = request.get_json(silent=True) or {}
    if not data:
        return {"error": "no fields to update"}, 400
    try:
        fields = _parse_task_payload(data, partial=True)
    except ValueError as exc:
        return {"error": str(exc)}, 400

    if not fields:
        return {"error": "no valid fields to update"}, 400

    db = get_db()
    assignments = ", ".join(f"{col} = ?" for col in fields)
    assignments += ", updated_at = strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now')"
    values = list(fields.values())
    db.execute(
        f"UPDATE tasks SET {assignments} WHERE id = ?", values + [task_id]
    )
    db.commit()
    return jsonify(task_to_dict(_fetch_task(task_id)))


@bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    row = _fetch_task(task_id)
    if row is None:
        return {"error": "task not found"}, 404
    user_id = _current_user_id()
    if row["creator_id"] != user_id:
        return {"error": "forbidden: only the creator may delete this task"}, 403
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return {"message": "task deleted"}, 200


@bp.post("/<int:task_id>/assign")
@jwt_required()
def assign_task(task_id):
    row = _fetch_task(task_id)
    if row is None:
        return {"error": "task not found"}, 404
    user_id = _current_user_id()
    if row["creator_id"] != user_id:
        return {"error": "forbidden: only the creator may assign this task"}, 403

    data = request.get_json(silent=True) or {}
    assignee_id = data.get("assignee_id")
    username = data.get("username")
    db = get_db()
    if assignee_id is None and username is None:
        return {"error": "assignee_id or username is required"}, 400
    if assignee_id is not None:
        user = db.execute("SELECT id FROM users WHERE id = ?", (int(assignee_id),)).fetchone()
    else:
        user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if user is None:
        return {"error": "user not found"}, 404

    db.execute(
        "UPDATE tasks SET assignee_id = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%S.%fZ', 'now') WHERE id = ?",
        (user["id"], task_id),
    )
    db.commit()
    return jsonify(task_to_dict(_fetch_task(task_id)))
