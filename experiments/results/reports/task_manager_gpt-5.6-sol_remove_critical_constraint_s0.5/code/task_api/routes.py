from __future__ import annotations

from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, request

from .db import get_db

api = Blueprint("api", __name__)

STATUSES = {"todo", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high"}
WRITABLE_FIELDS = {"title", "description", "status", "priority", "due_date"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def task_to_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def validation_error(errors: dict):
    return jsonify(error={"code": "Validation Error", "message": "Invalid request data", "fields": errors}), 400


def parse_json_object():
    if not request.is_json:
        return None, (jsonify(error={"code": "Unsupported Media Type", "message": "Content-Type must be application/json"}), 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, validation_error({"body": "must be a JSON object"})
    return data, None


def validate_task(data: dict, *, partial: bool = False) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    clean: dict = {}
    unknown = sorted(set(data) - WRITABLE_FIELDS)
    if unknown:
        errors["unknown"] = f"unsupported field(s): {', '.join(unknown)}"

    if not partial and "title" not in data:
        errors["title"] = "is required"
    if "title" in data:
        if not isinstance(data["title"], str):
            errors["title"] = "must be a string"
        elif not data["title"].strip():
            errors["title"] = "must not be empty"
        elif len(data["title"].strip()) > 200:
            errors["title"] = "must be at most 200 characters"
        else:
            clean["title"] = data["title"].strip()

    if "description" in data:
        if data["description"] is not None and not isinstance(data["description"], str):
            errors["description"] = "must be a string or null"
        else:
            clean["description"] = data["description"]

    if "status" in data:
        if data["status"] not in STATUSES:
            errors["status"] = f"must be one of: {', '.join(sorted(STATUSES))}"
        else:
            clean["status"] = data["status"]

    if "priority" in data:
        if data["priority"] not in PRIORITIES:
            errors["priority"] = f"must be one of: {', '.join(sorted(PRIORITIES))}"
        else:
            clean["priority"] = data["priority"]

    if "due_date" in data:
        value = data["due_date"]
        if value is None:
            clean["due_date"] = None
        elif not isinstance(value, str):
            errors["due_date"] = "must be an ISO date (YYYY-MM-DD) or null"
        else:
            try:
                clean["due_date"] = date.fromisoformat(value).isoformat()
            except ValueError:
                errors["due_date"] = "must be an ISO date (YYYY-MM-DD) or null"

    return clean, errors


def fetch_task(task_id: int):
    return get_db().execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def missing_task():
    return jsonify(error={"code": "Not Found", "message": "Task not found"}), 404


@api.get("/health")
def health():
    return jsonify(status="ok")


@api.post("/tasks")
def create_task():
    data, error = parse_json_object()
    if error:
        return error
    clean, errors = validate_task(data)
    if errors:
        return validation_error(errors)

    now = utc_now()
    status = clean.get("status", "todo")
    completed_at = now if status == "completed" else None
    db = get_db()
    cursor = db.execute(
        "INSERT INTO tasks (title, description, status, priority, due_date, completed_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            clean["title"], clean.get("description"), status,
            clean.get("priority", "medium"), clean.get("due_date"),
            completed_at, now, now,
        ),
    )
    db.commit()
    response = jsonify(task_to_dict(fetch_task(cursor.lastrowid)))
    response.status_code = 201
    response.headers["Location"] = f"/tasks/{cursor.lastrowid}"
    return response


@api.get("/tasks")
def list_tasks():
    errors = {}
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        page = 1
        per_page = 20
        if not request.args.get("page", "1").lstrip("+-").isdigit():
            errors["page"] = "must be a positive integer"
        if not request.args.get("per_page", "20").lstrip("+-").isdigit():
            errors["per_page"] = "must be an integer between 1 and 100"
    if page < 1:
        errors["page"] = "must be a positive integer"
    if not 1 <= per_page <= 100:
        errors["per_page"] = "must be an integer between 1 and 100"

    status = request.args.get("status")
    priority = request.args.get("priority")
    if status is not None and status not in STATUSES:
        errors["status"] = f"must be one of: {', '.join(sorted(STATUSES))}"
    if priority is not None and priority not in PRIORITIES:
        errors["priority"] = f"must be one of: {', '.join(sorted(PRIORITIES))}"

    sort = request.args.get("sort", "created_at")
    direction = request.args.get("direction", "desc")
    sort_fields = {"created_at", "updated_at", "due_date", "title", "priority", "status"}
    if sort not in sort_fields:
        errors["sort"] = f"must be one of: {', '.join(sorted(sort_fields))}"
    if direction not in {"asc", "desc"}:
        errors["direction"] = "must be one of: asc, desc"
    if errors:
        return validation_error(errors)

    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if priority:
        clauses.append("priority = ?")
        params.append(priority)
    if request.args.get("due_before"):
        try:
            due_before = date.fromisoformat(request.args["due_before"]).isoformat()
            clauses.append("due_date <= ?")
            params.append(due_before)
        except ValueError:
            return validation_error({"due_before": "must be an ISO date (YYYY-MM-DD)"})
    search = request.args.get("q", "").strip()
    if search:
        clauses.append("(title LIKE ? COLLATE NOCASE OR description LIKE ? COLLATE NOCASE)")
        pattern = f"%{search}%"
        params.extend((pattern, pattern))

    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM tasks{where}", params).fetchone()[0]
    offset = (page - 1) * per_page
    rows = db.execute(
        f"SELECT * FROM tasks{where} ORDER BY {sort} {direction.upper()}, id {direction.upper()} LIMIT ? OFFSET ?",
        (*params, per_page, offset),
    ).fetchall()
    return jsonify(
        items=[task_to_dict(row) for row in rows],
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page,
        },
    )


@api.get("/tasks/<int:task_id>")
def get_task(task_id: int):
    task = fetch_task(task_id)
    return jsonify(task_to_dict(task)) if task else missing_task()


def update_existing_task(task_id: int, *, partial: bool):
    existing = fetch_task(task_id)
    if not existing:
        return missing_task()
    data, error = parse_json_object()
    if error:
        return error
    if partial and not data:
        return validation_error({"body": "must include at least one field"})
    clean, errors = validate_task(data, partial=partial)
    if errors:
        return validation_error(errors)

    if not partial:
        clean.setdefault("description", None)
        clean.setdefault("status", "todo")
        clean.setdefault("priority", "medium")
        clean.setdefault("due_date", None)

    old_status = existing["status"]
    new_status = clean.get("status", old_status)
    if new_status == "completed" and old_status != "completed":
        clean["completed_at"] = utc_now()
    elif new_status != "completed" and old_status == "completed":
        clean["completed_at"] = None

    clean["updated_at"] = utc_now()
    assignments = ", ".join(f"{field} = ?" for field in clean)
    get_db().execute(
        f"UPDATE tasks SET {assignments} WHERE id = ?",
        (*clean.values(), task_id),
    )
    get_db().commit()
    return jsonify(task_to_dict(fetch_task(task_id)))


@api.put("/tasks/<int:task_id>")
def replace_task(task_id: int):
    return update_existing_task(task_id, partial=False)


@api.patch("/tasks/<int:task_id>")
def update_task(task_id: int):
    return update_existing_task(task_id, partial=True)


@api.post("/tasks/<int:task_id>/complete")
def complete_task(task_id: int):
    task = fetch_task(task_id)
    if not task:
        return missing_task()
    if task["status"] != "completed":
        now = utc_now()
        db = get_db()
        db.execute(
            "UPDATE tasks SET status = 'completed', completed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, task_id),
        )
        db.commit()
    return jsonify(task_to_dict(fetch_task(task_id)))


@api.delete("/tasks/<int:task_id>")
def delete_task(task_id: int):
    db = get_db()
    cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    if cursor.rowcount == 0:
        return missing_task()
    return "", 204
