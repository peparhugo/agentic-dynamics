import sqlite3
from datetime import date

from flask import Blueprint, g, jsonify, request

from . import get_db
from .security import auth_required

tasks_bp = Blueprint("tasks", __name__)
STATUSES = {"todo", "in_progress", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def _task(row):
    return dict(row)


def _validate(data, partial=False):
    errors = {}
    if not partial or "title" in data:
        if not isinstance(data.get("title"), str) or not data["title"].strip(): errors["title"] = "Title is required"
    for key, allowed in (("status", STATUSES), ("priority", PRIORITIES)):
        if key in data and data[key] not in allowed: errors[key] = f"Must be one of: {', '.join(sorted(allowed))}"
    if "due_date" in data and data["due_date"] is not None:
        try: date.fromisoformat(data["due_date"])
        except (TypeError, ValueError): errors["due_date"] = "Must be an ISO date (YYYY-MM-DD)"
    if "assignee_id" in data and data["assignee_id"] is not None and not isinstance(data["assignee_id"], int): errors["assignee_id"] = "Must be a user ID"
    return errors


@tasks_bp.get("")
@auth_required
def list_tasks():
    args = request.args
    conditions, params = ["(owner_id = ? OR assignee_id = ?)"], [g.user_id, g.user_id]
    for key in ("status", "category", "priority"):
        if args.get(key): conditions.append(f"{key} = ?"); params.append(args[key])
    if args.get("search"):
        conditions.append("(title LIKE ? OR description LIKE ?)"); term = f"%{args['search']}%"; params.extend([term, term])
    try: page, per_page = max(1, int(args.get("page", 1))), min(100, max(1, int(args.get("per_page", 20))))
    except ValueError: return jsonify(error="validation_error", message="page and per_page must be integers"), 400
    db = get_db(); where = " AND ".join(conditions)
    total = db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
    rows = db.execute(f"SELECT * FROM tasks WHERE {where} ORDER BY due_date IS NULL, due_date, id DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
    return jsonify(items=[_task(row) for row in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page})


@tasks_bp.post("")
@auth_required
def create_task():
    data = request.get_json(silent=True) or {}; errors = _validate(data)
    if errors: return jsonify(error="validation_error", fields=errors), 400
    assignee = data.get("assignee_id")
    db = get_db()
    if assignee is not None and not db.execute("SELECT id FROM users WHERE id = ?", (assignee,)).fetchone(): return jsonify(error="validation_error", message="Assignee does not exist"), 400
    cursor = db.execute("INSERT INTO tasks (title, description, status, category, priority, due_date, owner_id, assignee_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (data["title"].strip(), data.get("description", ""), data.get("status", "todo"), data.get("category", "general"), data.get("priority", "medium"), data.get("due_date"), g.user_id, assignee))
    db.commit(); return jsonify(task=_task(db.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone())), 201


def _owned(task_id):
    return get_db().execute("SELECT * FROM tasks WHERE id = ? AND (owner_id = ? OR assignee_id = ?)", (task_id, g.user_id, g.user_id)).fetchone()


@tasks_bp.get("/<int:task_id>")
@auth_required
def get_task(task_id):
    row = _owned(task_id)
    return (jsonify(task=_task(row)) if row else (jsonify(error="not_found", message="Task not found"), 404))


@tasks_bp.route("/<int:task_id>", methods=["PUT", "PATCH"])
@auth_required
def update_task(task_id):
    if not _owned(task_id): return jsonify(error="not_found", message="Task not found"), 404
    data = request.get_json(silent=True) or {}; errors = _validate(data, partial=True)
    if errors: return jsonify(error="validation_error", fields=errors), 400
    allowed = {key: data[key] for key in ("title", "description", "status", "category", "priority", "due_date", "assignee_id") if key in data}
    if not allowed: return jsonify(error="validation_error", message="No fields to update"), 400
    if "assignee_id" in allowed and allowed["assignee_id"] is not None and not get_db().execute("SELECT id FROM users WHERE id = ?", (allowed["assignee_id"],)).fetchone(): return jsonify(error="validation_error", message="Assignee does not exist"), 400
    fields = list(allowed); values = [allowed[key] for key in fields]
    if "title" in allowed: values[fields.index("title")] = allowed["title"].strip()
    db = get_db(); db.execute(f"UPDATE tasks SET {', '.join(f'{key} = ?' for key in fields)}, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?", values + [task_id]); db.commit()
    return jsonify(task=_task(db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()))


@tasks_bp.delete("/<int:task_id>")
@auth_required
def delete_task(task_id):
    if not _owned(task_id): return jsonify(error="not_found", message="Task not found"), 404
    db = get_db(); db.execute("DELETE FROM tasks WHERE id = ?", (task_id,)); db.commit(); return "", 204
