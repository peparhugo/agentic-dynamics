from datetime import date

from flask import Blueprint, g, jsonify, request

from . import db, now_iso
from .auth import auth_required

tasks_bp = Blueprint("tasks", __name__)
STATUSES = {"todo", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high", "urgent"}
FIELDS = {"title", "description", "status", "category", "priority", "due_date", "assignee_id"}


def serialize(row):
    result = dict(row)
    result["assignee"] = None
    if result.get("assignee_id"):
        user = db().execute("SELECT id, email, name FROM users WHERE id = ?", (result["assignee_id"],)).fetchone()
        result["assignee"] = dict(user) if user else None
    return result


def validate(data, partial=False):
    if not partial and (not isinstance(data.get("title"), str) or not data["title"].strip()):
        return "title is required"
    for field in ("status", "priority"):
        if field in data and data[field] not in (STATUSES if field == "status" else PRIORITIES):
            return f"invalid {field}"
    if "due_date" in data and data["due_date"] is not None:
        try:
            date.fromisoformat(data["due_date"])
        except (TypeError, ValueError):
            return "due_date must be an ISO date (YYYY-MM-DD)"
    if "assignee_id" in data and data["assignee_id"] is not None:
        try:
            assigned = db().execute("SELECT id FROM users WHERE id = ?", (int(data["assignee_id"]),)).fetchone()
        except (TypeError, ValueError):
            assigned = None
        if assigned is None:
            return "assignee_id does not reference a user"
    return None


@tasks_bp.get("/categories")
def categories():
    return jsonify(categories=[row[0] for row in db().execute("SELECT DISTINCT category FROM tasks ORDER BY category")])


@tasks_bp.get("/priorities")
def priorities():
    return jsonify(priorities=sorted(PRIORITIES))


@tasks_bp.route("/tasks", methods=["GET", "POST"])
@auth_required
def task_collection():
    connection = db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        error = validate(data)
        if error:
            return jsonify(error=error), 400
        timestamp = now_iso()
        values = (g.user["id"], data.get("assignee_id"), data["title"].strip(), data.get("description", ""),
                  data.get("status", "todo"), data.get("category", "general").strip(), data.get("priority", "medium"),
                  data.get("due_date"), timestamp, timestamp)
        cursor = connection.execute("""INSERT INTO tasks(user_id, assignee_id, title, description, status, category,
            priority, due_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", values)
        connection.commit()
        return jsonify(task=serialize(connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone())), 201

    clauses = ["(t.user_id = ? OR t.assignee_id = ?)"]
    params = [g.user["id"], g.user["id"]]
    for field in ("status", "category", "priority"):
        if request.args.get(field):
            clauses.append(f"t.{field} = ?")
            params.append(request.args[field])
    search = request.args.get("search", request.args.get("q", "")).strip()
    if search:
        clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    try:
        page, per_page = max(int(request.args.get("page", 1)), 1), min(max(int(request.args.get("per_page", 20)), 1), 100)
    except ValueError:
        return jsonify(error="page and per_page must be integers"), 400
    where = " AND ".join(clauses)
    total = connection.execute(f"SELECT COUNT(*) FROM tasks t WHERE {where}", params).fetchone()[0]
    rows = connection.execute(f"SELECT t.* FROM tasks t WHERE {where} ORDER BY t.created_at DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
    return jsonify(tasks=[serialize(row) for row in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page})


@tasks_bp.route("/tasks/<int:task_id>", methods=["GET", "PATCH", "PUT", "DELETE"])
@auth_required
def task_item(task_id):
    connection = db()
    row = connection.execute("SELECT * FROM tasks WHERE id = ? AND (user_id = ? OR assignee_id = ?)", (task_id, g.user["id"], g.user["id"])).fetchone()
    if row is None:
        return jsonify(error="task not found"), 404
    if request.method == "GET":
        return jsonify(task=serialize(row))
    if request.method == "DELETE":
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,)); connection.commit()
        return "", 204
    data = request.get_json(silent=True) or {}
    unknown = set(data) - FIELDS
    if unknown:
        return jsonify(error=f"unknown fields: {', '.join(sorted(unknown))}"), 400
    error = validate(data, partial=True)
    if error:
        return jsonify(error=error), 400
    if "title" in data and (not isinstance(data["title"], str) or not data["title"].strip()):
        return jsonify(error="title cannot be empty"), 400
    updates, params = [], []
    for field in FIELDS:
        if field in data:
            updates.append(f"{field} = ?")
            params.append(data[field].strip() if field in ("title", "category") and isinstance(data[field], str) else data[field])
    if not updates:
        return jsonify(error="no fields to update"), 400
    updates.append("updated_at = ?"); params.extend([now_iso(), task_id])
    connection.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params); connection.commit()
    return jsonify(task=serialize(connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()))
