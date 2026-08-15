from datetime import date as date_cls
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from .db import get_db
from .errors import ApiError

api = Blueprint("api", __name__)

VALID_STATUSES = {"pending", "in_progress", "completed"}
VALID_SORTS = {"id", "title", "status", "priority", "due_date", "created_at", "updated_at"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _row_to_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "due_date": row["due_date"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_json_body():
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError("request body must be valid JSON")
    if not isinstance(data, dict):
        raise ApiError("request body must be a JSON object")
    return data


def _parse_int(value, default, name, minimum=None):
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be an integer")
    if minimum is not None and parsed < minimum:
        raise ApiError(f"{name} must be at least {minimum}")
    return parsed


def _clean_title(value):
    if not isinstance(value, str) or not value.strip():
        raise ApiError("title is required and must be a non-empty string")
    title = value.strip()
    if len(title) > 200:
        raise ApiError("title must be at most 200 characters")
    return title


def _clean_description(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError("description must be a string")
    return value.strip()


def _clean_status(value):
    if value not in VALID_STATUSES:
        raise ApiError(f"status must be one of {', '.join(sorted(VALID_STATUSES))}")
    return value


def _clean_priority(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
        raise ApiError("priority must be an integer between 1 and 5")
    return value


def _clean_due_date(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError("due_date must be an ISO date string (YYYY-MM-DD)")
    raw = value.strip()
    if len(raw) != 10:
        raise ApiError("due_date must be an ISO date string (YYYY-MM-DD)")
    try:
        parsed = date_cls.fromisoformat(raw)
    except ValueError:
        raise ApiError("due_date must be a valid ISO date string (YYYY-MM-DD)")
    return parsed.isoformat()


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "task-api"})


@api.route("/tasks", methods=["GET"])
def list_tasks():
    db = get_db()
    conditions = []
    params = []

    status = request.args.get("status")
    if status is not None:
        conditions.append("status = ?")
        params.append(_clean_status(status))

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        params.extend([like, like])
        conditions.append("(title LIKE ? OR description LIKE ?)")

    sort = request.args.get("sort", "created_at")
    if sort not in VALID_SORTS:
        raise ApiError(f"sort must be one of {', '.join(sorted(VALID_SORTS))}")
    order = request.args.get("order", "asc")
    if order not in ("asc", "desc"):
        raise ApiError("order must be 'asc' or 'desc'")
    direction = "ASC" if order == "asc" else "DESC"

    page = _parse_int(request.args.get("page"), 1, "page", minimum=1)
    per_page = _parse_int(request.args.get("per_page"), 20, "per_page", minimum=1)
    per_page = min(per_page, 100)

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    total = db.execute(
        f"SELECT COUNT(*) AS count FROM tasks{where}", params
    ).fetchone()["count"]
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM tasks{where} ORDER BY {sort} {direction} LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    return jsonify(
        {
            "items": [_row_to_task(r) for r in rows],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    )


@api.route("/tasks", methods=["POST"])
def create_task():
    data = _get_json_body()
    title = _clean_title(data.get("title"))
    description = _clean_description(data.get("description"))
    status = _clean_status(data.get("status", "pending"))
    priority = _clean_priority(data.get("priority", 3))
    due_date = _clean_due_date(data.get("due_date"))
    now = _now()

    db = get_db()
    cur = db.execute(
        "INSERT INTO tasks (title, description, status, priority, due_date, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, description, status, priority, due_date, now, now),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(_row_to_task(row)), 201


@api.route("/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    row = get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ApiError("task not found", 404)
    return jsonify(_row_to_task(row))


@api.route("/tasks/<int:task_id>", methods=["PUT", "PATCH"])
def update_task(task_id):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise ApiError("task not found", 404)

    data = _get_json_body()
    current = dict(row)
    partial = request.method == "PATCH"

    if partial:
        if "title" in data:
            current["title"] = _clean_title(data["title"])
        if "description" in data:
            current["description"] = _clean_description(data["description"])
        if "status" in data:
            current["status"] = _clean_status(data["status"])
        if "priority" in data:
            current["priority"] = _clean_priority(data["priority"])
        if "due_date" in data:
            current["due_date"] = _clean_due_date(data["due_date"])
    else:
        current["title"] = _clean_title(data.get("title"))
        current["description"] = _clean_description(data.get("description"))
        current["status"] = _clean_status(data.get("status", "pending"))
        current["priority"] = _clean_priority(data.get("priority", 3))
        current["due_date"] = _clean_due_date(data.get("due_date"))

    now = _now()
    db.execute(
        "UPDATE tasks SET title = ?, description = ?, status = ?, priority = ?,"
        " due_date = ?, updated_at = ? WHERE id = ?",
        (
            current["title"],
            current["description"],
            current["status"],
            current["priority"],
            current["due_date"],
            now,
            task_id,
        ),
    )
    db.commit()
    updated = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return jsonify(_row_to_task(updated))


@api.route("/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    db = get_db()
    cur = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    if cur.rowcount == 0:
        raise ApiError("task not found", 404)
    return jsonify({"message": "task deleted", "id": task_id})
