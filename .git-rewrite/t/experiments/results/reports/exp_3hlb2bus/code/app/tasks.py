"""Task CRUD, assignment, search/filter, and pagination.

Visibility rule: a user can see/modify tasks they created or are assigned to.
Only the creator may delete a task.
"""
import datetime

from flask import Blueprint, current_app, g, jsonify, request

from .auth import require_auth
from .db import get_db
from .errors import APIError

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

STATUSES = ("todo", "in_progress", "done")
PRIORITIES = ("low", "medium", "high", "urgent")
SORTABLE = {"created_at", "updated_at", "due_date", "priority", "title", "status", "id"}
MAX_TITLE_LEN = 200
MAX_DESCRIPTION_LEN = 5000

TASK_SELECT = """
    SELECT t.*,
           c.name  AS category_name,
           cu.username AS creator_username,
           au.username AS assignee_username
      FROM tasks t
 LEFT JOIN categories c ON c.id = t.category_id
      JOIN users cu ON cu.id = t.creator_id
 LEFT JOIN users au ON au.id = t.assignee_id
"""


# --------------------------------------------------------------------------- serialization

def task_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"],
        "category": (
            {"id": row["category_id"], "name": row["category_name"]}
            if row["category_id"] else None
        ),
        "creator": {"id": row["creator_id"], "username": row["creator_username"]},
        "assignee": (
            {"id": row["assignee_id"], "username": row["assignee_username"]}
            if row["assignee_id"] else None
        ),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# --------------------------------------------------------------------------- validation

def _json_body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError("Request body must be a JSON object", 400)
    return data


def _parse_due_date(value):
    """Accept ISO-8601 date or datetime; store as ISO string. None clears it."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise APIError("due_date must be an ISO-8601 string or null", 400)
    text = value.strip()
    try:
        if len(text) == 10:  # date only
            return datetime.date.fromisoformat(text).isoformat()
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
    except ValueError:
        raise APIError("due_date must be a valid ISO-8601 date/datetime", 400)


def _validate_fields(data: dict, *, partial: bool) -> dict:
    """Validate incoming fields; return dict of column -> value to set."""
    fields = {}
    db = get_db()

    if "title" in data or not partial:
        title = str(data.get("title", "") or "").strip()
        if not title or len(title) > MAX_TITLE_LEN:
            raise APIError(f"title is required (1-{MAX_TITLE_LEN} chars)", 400)
        fields["title"] = title

    if "description" in data:
        description = data["description"]
        if description is None:
            description = ""
        if not isinstance(description, str) or len(description) > MAX_DESCRIPTION_LEN:
            raise APIError(f"description must be a string (max {MAX_DESCRIPTION_LEN} chars)", 400)
        fields["description"] = description

    if "status" in data:
        if data["status"] not in STATUSES:
            raise APIError(f"status must be one of {list(STATUSES)}", 400)
        fields["status"] = data["status"]

    if "priority" in data:
        if data["priority"] not in PRIORITIES:
            raise APIError(f"priority must be one of {list(PRIORITIES)}", 400)
        fields["priority"] = data["priority"]

    if "due_date" in data:
        fields["due_date"] = _parse_due_date(data["due_date"])

    if "category_id" in data:
        category_id = data["category_id"]
        if category_id is not None:
            if not isinstance(category_id, int):
                raise APIError("category_id must be an integer or null", 400)
            owned = db.execute(
                "SELECT 1 FROM categories WHERE id = ? AND user_id = ?",
                (category_id, g.current_user["id"]),
            ).fetchone()
            if not owned:
                raise APIError("Category not found", 404)
        fields["category_id"] = category_id

    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is not None:
            if not isinstance(assignee_id, int):
                raise APIError("assignee_id must be an integer or null", 400)
            if not db.execute("SELECT 1 FROM users WHERE id = ?", (assignee_id,)).fetchone():
                raise APIError("Assignee user not found", 404)
        fields["assignee_id"] = assignee_id

    return fields


def _get_visible_task(task_id: int):
    row = get_db().execute(
        TASK_SELECT + " WHERE t.id = ? AND (t.creator_id = ? OR t.assignee_id = ?)",
        (task_id, g.current_user["id"], g.current_user["id"]),
    ).fetchone()
    if row is None:
        raise APIError("Task not found", 404)
    return row


def _fetch_task(task_id: int):
    return get_db().execute(TASK_SELECT + " WHERE t.id = ?", (task_id,)).fetchone()


# --------------------------------------------------------------------------- routes

@bp.post("")
@require_auth
def create_task():
    data = _json_body()
    fields = _validate_fields(data, partial=False)
    fields.setdefault("description", "")
    fields.setdefault("status", "todo")
    fields.setdefault("priority", "medium")
    fields.setdefault("due_date", None)
    fields.setdefault("category_id", None)
    fields.setdefault("assignee_id", None)

    db = get_db()
    cur = db.execute(
        """INSERT INTO tasks (title, description, status, priority, due_date,
                              category_id, creator_id, assignee_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (fields["title"], fields["description"], fields["status"], fields["priority"],
         fields["due_date"], fields["category_id"], g.current_user["id"],
         fields["assignee_id"]),
    )
    db.commit()
    return jsonify({"task": task_to_dict(_fetch_task(cur.lastrowid))}), 201


@bp.get("")
@require_auth
def list_tasks():
    args = request.args
    where = ["(t.creator_id = :uid OR t.assignee_id = :uid)"]
    params = {"uid": g.current_user["id"]}

    if "status" in args:
        statuses = [s for s in args.get("status", "").split(",") if s]
        if not statuses or any(s not in STATUSES for s in statuses):
            raise APIError(f"status must be one of {list(STATUSES)}", 400)
        keys = [f"st{i}" for i in range(len(statuses))]
        where.append(f"t.status IN ({', '.join(':' + k for k in keys)})")
        params.update(dict(zip(keys, statuses)))

    if "priority" in args:
        priorities = [p for p in args.get("priority", "").split(",") if p]
        if not priorities or any(p not in PRIORITIES for p in priorities):
            raise APIError(f"priority must be one of {list(PRIORITIES)}", 400)
        keys = [f"pr{i}" for i in range(len(priorities))]
        where.append(f"t.priority IN ({', '.join(':' + k for k in keys)})")
        params.update(dict(zip(keys, priorities)))

    if "category_id" in args:
        category_id = args.get("category_id", type=int)
        if category_id is None:
            raise APIError("category_id must be an integer", 400)
        where.append("t.category_id = :category_id")
        params["category_id"] = category_id

    if "assignee_id" in args:
        assignee_id = args.get("assignee_id", type=int)
        if assignee_id is None:
            raise APIError("assignee_id must be an integer", 400)
        where.append("t.assignee_id = :assignee_id")
        params["assignee_id"] = assignee_id

    if args.get("q"):
        where.append("(t.title LIKE :q ESCAPE '\\' OR t.description LIKE :q ESCAPE '\\')")
        escaped = args["q"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        params["q"] = f"%{escaped}%"

    if args.get("due_before"):
        where.append("t.due_date IS NOT NULL AND t.due_date <= :due_before")
        params["due_before"] = _parse_due_date(args["due_before"])
    if args.get("due_after"):
        where.append("t.due_date IS NOT NULL AND t.due_date >= :due_after")
        params["due_after"] = _parse_due_date(args["due_after"])

    if args.get("overdue") in ("1", "true"):
        where.append("t.due_date IS NOT NULL AND t.due_date < :now AND t.status != 'done'")
        params["now"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    sort = args.get("sort", "created_at")
    if sort not in SORTABLE:
        raise APIError(f"sort must be one of {sorted(SORTABLE)}", 400)
    order = args.get("order", "desc").lower()
    if order not in ("asc", "desc"):
        raise APIError("order must be 'asc' or 'desc'", 400)
    if sort == "priority":
        order_clause = (
            "CASE t.priority WHEN 'urgent' THEN 4 WHEN 'high' THEN 3 "
            "WHEN 'medium' THEN 2 ELSE 1 END " + order.upper()
        )
    else:
        order_clause = f"t.{sort} {order.upper()}"
    order_clause += ", t.id " + order.upper()

    page = args.get("page", default=1, type=int) or 1
    if page < 1:
        raise APIError("page must be >= 1", 400)
    per_page = args.get("per_page", default=current_app.config["DEFAULT_PAGE_SIZE"], type=int)
    if per_page is None or per_page < 1:
        raise APIError("per_page must be >= 1", 400)
    per_page = min(per_page, current_app.config["MAX_PAGE_SIZE"])

    db = get_db()
    where_sql = " WHERE " + " AND ".join(where)
    total = db.execute(
        "SELECT COUNT(*) FROM tasks t" + where_sql, params
    ).fetchone()[0]
    params.update({"limit": per_page, "offset": (page - 1) * per_page})
    rows = db.execute(
        TASK_SELECT + where_sql + f" ORDER BY {order_clause} LIMIT :limit OFFSET :offset",
        params,
    ).fetchall()

    total_pages = max(1, -(-total // per_page))
    return jsonify({
        "tasks": [task_to_dict(r) for r in rows],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    })


@bp.get("/<int:task_id>")
@require_auth
def get_task(task_id):
    return jsonify({"task": task_to_dict(_get_visible_task(task_id))})


def _update(task_id, *, partial):
    _get_visible_task(task_id)
    data = _json_body()
    fields = _validate_fields(data, partial=partial)
    if not fields:
        raise APIError("No valid fields to update", 400)

    db = get_db()
    sets = ", ".join(f"{col} = :{col}" for col in fields)
    fields.update({"id": task_id, "now": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    db.execute(f"UPDATE tasks SET {sets}, updated_at = :now WHERE id = :id", fields)
    db.commit()
    return jsonify({"task": task_to_dict(_fetch_task(task_id))})


@bp.put("/<int:task_id>")
@require_auth
def replace_task(task_id):
    return _update(task_id, partial=False)


@bp.patch("/<int:task_id>")
@require_auth
def update_task(task_id):
    return _update(task_id, partial=True)


@bp.delete("/<int:task_id>")
@require_auth
def delete_task(task_id):
    row = _get_visible_task(task_id)
    if row["creator_id"] != g.current_user["id"]:
        raise APIError("Only the task creator can delete a task", 403)
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return "", 204


@bp.post("/<int:task_id>/assign")
@require_auth
def assign_task(task_id):
    _get_visible_task(task_id)
    data = _json_body()
    if "assignee_id" not in data:
        raise APIError("assignee_id is required (integer or null to unassign)", 400)
    fields = _validate_fields({"assignee_id": data["assignee_id"]}, partial=True)

    db = get_db()
    db.execute(
        "UPDATE tasks SET assignee_id = ?, updated_at = ? WHERE id = ?",
        (fields["assignee_id"],
         datetime.datetime.now(datetime.timezone.utc).isoformat(), task_id),
    )
    db.commit()
    return jsonify({"task": task_to_dict(_fetch_task(task_id))})
