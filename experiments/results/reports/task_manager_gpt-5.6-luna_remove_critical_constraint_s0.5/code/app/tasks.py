"""HTTP handlers for task resources."""

from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request

from .db import get_db

tasks_bp = Blueprint("tasks", __name__)
VALID_STATUSES = {"pending", "completed"}
VALID_PRIORITIES = {"low", "medium", "high"}
SORT_FIELDS = {"created_at", "updated_at", "title", "status", "priority", "due_date"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def error(message, status=400, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def serialize(row):
    return dict(row)


def parse_payload(payload, partial=False):
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    allowed = {"title", "description", "status", "priority", "due_date"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError("unknown fields: " + ", ".join(unknown))
    if not partial and "title" not in payload:
        raise ValueError("title is required")
    values = {}
    if "title" in payload:
        if not isinstance(payload["title"], str) or not payload["title"].strip():
            raise ValueError("title must be a non-empty string")
        if len(payload["title"]) > 200:
            raise ValueError("title must be at most 200 characters")
        values["title"] = payload["title"].strip()
    if "description" in payload:
        if not isinstance(payload["description"], str) or len(payload["description"]) > 2000:
            raise ValueError("description must be a string of at most 2000 characters")
        values["description"] = payload["description"]
    if "status" in payload:
        if payload["status"] not in VALID_STATUSES:
            raise ValueError("status must be pending or completed")
        values["status"] = payload["status"]
    if "priority" in payload:
        if payload["priority"] not in VALID_PRIORITIES:
            raise ValueError("priority must be low, medium, or high")
        values["priority"] = payload["priority"]
    if "due_date" in payload:
        due = payload["due_date"]
        if due is not None:
            if not isinstance(due, str):
                raise ValueError("due_date must be an ISO date or null")
            try:
                date.fromisoformat(due)
            except ValueError:
                raise ValueError("due_date must be an ISO date or null")
        values["due_date"] = due
    return values


@tasks_bp.get("/tasks")
def list_tasks():
    db = get_db()
    clauses, params = [], []
    for field, allowed in (("status", VALID_STATUSES), ("priority", VALID_PRIORITIES)):
        value = request.args.get(field)
        if value:
            if value not in allowed:
                return error(f"invalid {field}", details=sorted(allowed))
            clauses.append(f"{field} = ?")
            params.append(value)
    query = request.args.get("q")
    if query:
        clauses.append("(title LIKE ? OR description LIKE ?)")
        params.extend((f"%{query}%", f"%{query}%"))
    for field, operator in (("due_before", "<="), ("due_after", ">=")):
        value = request.args.get(field)
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                return error(f"{field} must be an ISO date")
            clauses.append(f"due_date {operator} ?")
            params.append(value)
    try:
        page, per_page = int(request.args.get("page", 1)), int(request.args.get("per_page", 20))
    except ValueError:
        return error("page and per_page must be integers")
    if page < 1 or not 1 <= per_page <= 100:
        return error("page must be at least 1 and per_page must be between 1 and 100")
    sort = request.args.get("sort", "created_at")
    if sort not in SORT_FIELDS:
        return error("invalid sort", details=sorted(SORT_FIELDS))
    order = request.args.get("order", "desc").lower()
    if order not in {"asc", "desc"}:
        return error("order must be asc or desc")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    total = db.execute(f"SELECT COUNT(*) FROM tasks{where}", params).fetchone()[0]
    rows = db.execute(
        f"SELECT * FROM tasks{where} ORDER BY {sort} {order.upper()}, id DESC LIMIT ? OFFSET ?",
        [*params, per_page, (page - 1) * per_page],
    ).fetchall()
    return jsonify({"data": [serialize(row) for row in rows], "page": page, "per_page": per_page, "total": total})


@tasks_bp.post("/tasks")
def create_task():
    try:
        values = parse_payload(request.get_json(silent=True) or {})
    except ValueError as exc:
        return error(str(exc))
    timestamp = now()
    values.setdefault("description", "")
    values.setdefault("status", "pending")
    values.setdefault("priority", "medium")
    values.setdefault("due_date", None)
    db = get_db()
    cursor = db.execute(
        "INSERT INTO tasks (title, description, status, priority, due_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (*[values[key] for key in ("title", "description", "status", "priority", "due_date")], timestamp, timestamp),
    )
    db.commit()
    return jsonify(serialize(db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone())), 201


@tasks_bp.get("/tasks/<int:task_id>")
def get_task(task_id):
    row = get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return (jsonify(serialize(row)), 200) if row else error("task not found", 404)


@tasks_bp.patch("/tasks/<int:task_id>")
def update_task(task_id):
    db = get_db()
    if not db.execute("SELECT 1 FROM tasks WHERE id = ?", (task_id,)).fetchone():
        return error("task not found", 404)
    try:
        values = parse_payload(request.get_json(silent=True), partial=True)
    except ValueError as exc:
        return error(str(exc))
    if not values:
        return error("at least one field is required")
    values["updated_at"] = now()
    assignments = ", ".join(f"{key} = ?" for key in values)
    db.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", [*values.values(), task_id])
    db.commit()
    return jsonify(serialize(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()))


@tasks_bp.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    db = get_db()
    cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    if cursor.rowcount == 0:
        return error("task not found", 404)
    return "", 204
