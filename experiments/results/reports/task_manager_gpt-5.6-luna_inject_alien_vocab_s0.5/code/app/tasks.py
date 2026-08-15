from datetime import date

from flask import Blueprint, g, jsonify, request

from .auth import current_user_required
from .db import get_db

bp = Blueprint("tasks", __name__)
STATUSES = {"todo", "in_progress", "done"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def category_json(row):
    return {"id": row["id"], "name": row["name"]}


def task_json(row):
    result = dict(row)
    result["category"] = {"id": row["category_id"], "name": row["category_name"]} if row["category_id"] else None
    result["assignee"] = {"id": row["assignee_id"], "email": row["assignee_email"], "name": row["assignee_name"]} if row["assignee_id"] else None
    result.pop("category_id", None)
    result.pop("category_name", None)
    result.pop("assignee_id", None)
    result.pop("assignee_email", None)
    result.pop("assignee_name", None)
    return result


TASK_SELECT = """SELECT t.*, c.name category_name, u.email assignee_email, u.name assignee_name
FROM tasks t LEFT JOIN categories c ON c.id=t.category_id LEFT JOIN users u ON u.id=t.assignee_id"""


@bp.get("/api/categories")
@current_user_required
def categories():
    rows = get_db().execute("SELECT id, name FROM categories WHERE user_id=? ORDER BY name", (g.user["id"],)).fetchall()
    return jsonify(categories=[category_json(row) for row in rows])


@bp.post("/api/categories")
@current_user_required
def create_category():
    name = (request.get_json(silent=True) or {}).get("name", "")
    if not isinstance(name, str) or not name.strip():
        return jsonify(error="category name is required"), 400
    db = get_db()
    try:
        cursor = db.execute("INSERT INTO categories(user_id,name) VALUES (?,?)", (g.user["id"], name.strip()))
        db.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            return jsonify(error="category already exists"), 409
        raise
    return jsonify(category={"id": cursor.lastrowid, "name": name.strip()}), 201


def validate_payload(data, partial=False):
    allowed = {"title", "description", "status", "priority", "due_date", "category_id", "assigned_to"}
    unknown = set(data) - allowed
    if unknown:
        return "unknown fields: " + ", ".join(sorted(unknown))
    if not partial or "title" in data:
        if not isinstance(data.get("title"), str) or not data["title"].strip(): return "title is required"
    if "status" in data and data["status"] not in STATUSES: return "invalid status"
    if "priority" in data and data["priority"] not in PRIORITIES: return "invalid priority"
    if "due_date" in data and data["due_date"] is not None:
        try: date.fromisoformat(data["due_date"])
        except (TypeError, ValueError): return "due_date must be YYYY-MM-DD"
    return None


def related_ids_valid(data):
    db = get_db()
    category_id = data.get("category_id")
    if category_id is not None and db.execute("SELECT 1 FROM categories WHERE id=? AND user_id=?", (category_id, g.user["id"])).fetchone() is None: return "category not found"
    assignee = data.get("assigned_to")
    if assignee is not None and db.execute("SELECT 1 FROM users WHERE id=?", (assignee,)).fetchone() is None: return "assignee not found"
    return None


@bp.route("/api/tasks", methods=["GET", "POST"])
@current_user_required
def task_collection():
    db = get_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        error = validate_payload(data) or related_ids_valid(data)
        if error: return jsonify(error=error), 400
        values = (g.user["id"], data["title"].strip(), data.get("description", ""), data.get("status", "todo"), data.get("priority", "medium"), data.get("due_date"), data.get("category_id"), data.get("assigned_to"))
        cur = db.execute("INSERT INTO tasks(user_id,title,description,status,priority,due_date,category_id,assignee_id) VALUES (?,?,?,?,?,?,?,?)", values)
        db.commit()
        row = db.execute(TASK_SELECT + " WHERE t.id=?", (cur.lastrowid,)).fetchone()
        return jsonify(task=task_json(row)), 201
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)
    clauses, params = ["t.user_id=?"], [g.user["id"]]
    for field in ("status", "priority"):
        if request.args.get(field): clauses.append("t." + field + "=?"); params.append(request.args[field])
    if request.args.get("category"): clauses.append("c.name=?"); params.append(request.args["category"])
    if request.args.get("search"): clauses.append("(t.title LIKE ? OR t.description LIKE ?)"); params.extend(["%" + request.args["search"] + "%"] * 2)
    where = " WHERE " + " AND ".join(clauses)
    total = db.execute("SELECT COUNT(*) FROM tasks t LEFT JOIN categories c ON c.id=t.category_id" + where, params).fetchone()[0]
    rows = db.execute(TASK_SELECT + where + " ORDER BY t.created_at DESC, t.id DESC LIMIT ? OFFSET ?", params + [per_page, (page - 1) * per_page]).fetchall()
    return jsonify(tasks=[task_json(row) for row in rows], pagination={"page": page, "per_page": per_page, "total": total, "pages": (total + per_page - 1) // per_page})


@bp.route("/api/tasks/<int:task_id>", methods=["GET", "PATCH", "DELETE"])
@current_user_required
def task_detail(task_id):
    db = get_db()
    row = db.execute(TASK_SELECT + " WHERE t.id=? AND t.user_id=?", (task_id, g.user["id"])).fetchone()
    if row is None: return jsonify(error="task not found"), 404
    if request.method == "GET": return jsonify(task=task_json(row))
    if request.method == "DELETE": db.execute("DELETE FROM tasks WHERE id=?", (task_id,)); db.commit(); return "", 204
    data = request.get_json(silent=True) or {}
    error = validate_payload(data, partial=True) or related_ids_valid(data)
    if error: return jsonify(error=error), 400
    names = {"title": "title", "description": "description", "status": "status", "priority": "priority", "due_date": "due_date", "category_id": "category_id", "assigned_to": "assignee_id"}
    if not data: return jsonify(task=task_json(row))
    assignments = [names[key] + "=?" for key in data]
    values = [data[key].strip() if key == "title" else data[key] for key in data]
    assignments.append("updated_at=datetime('now')")
    db.execute("UPDATE tasks SET " + ",".join(assignments) + " WHERE id=?", values + [task_id]); db.commit()
    return jsonify(task=task_json(db.execute(TASK_SELECT + " WHERE t.id=?", (task_id,)).fetchone()))
