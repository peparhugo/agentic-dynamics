from flask import Blueprint, jsonify, request, g

from app.auth import auth_required
from app.db import get_db, row_to_dict

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")

VALID_STATUSES = ("todo", "in_progress", "done")
VALID_PRIORITIES = ("low", "medium", "high")


def _task_select(alias="t"):
    return (
        f"SELECT {alias}.*, "
        f"u.username AS created_by_username, a.username AS assigned_to_username "
        f"FROM tasks {alias} "
        f"LEFT JOIN users u ON u.id = {alias}.created_by "
        f"LEFT JOIN users a ON a.id = {alias}.assigned_to"
    )


def _visible_tasks_where():
    return "(t.created_by = :uid OR t.assigned_to = :uid)"


def _resolve_category(db, user_id, category_id):
    if category_id is None:
        return None
    row = db.execute(
        "SELECT id FROM categories WHERE id = ? AND user_id = ?", (category_id, user_id)
    ).fetchone()
    if row is None:
        return None
    return row["id"]


@tasks_bp.post("")
@auth_required
def create_task():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    status = payload.get("status", "todo")
    priority = payload.get("priority", "medium")
    if status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {VALID_STATUSES}"}), 400
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"priority must be one of {VALID_PRIORITIES}"}), 400

    description = payload.get("description") or ""
    due_date = payload.get("due_date")
    db = get_db()

    category_id = _resolve_category(db, g.user["id"], payload.get("category_id"))
    assigned_to = payload.get("assigned_to")
    if assigned_to is not None:
        assignee = db.execute("SELECT id FROM users WHERE id = ?", (assigned_to,)).fetchone()
        if assignee is None:
            return jsonify({"error": "assigned_to user does not exist"}), 400

    cursor = db.execute(
        """INSERT INTO tasks (title, description, status, priority, due_date, category_id,
                              created_by, assigned_to, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (title, description, status, priority, due_date, category_id, g.user["id"], assigned_to),
    )
    db.commit()
    task = db.execute(
        f"{_task_select()} WHERE t.id = ?", (cursor.lastrowid,)
    ).fetchone()
    return jsonify({"task": row_to_dict(task)}), 201


@tasks_bp.get("")
@auth_required
def list_tasks():
    db = get_db()
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    per_page = min(max(request.args.get("per_page", 10, type=int) or 10, 1), 100)

    where = [_visible_tasks_where()]
    params = {"uid": g.user["id"]}

    status = request.args.get("status")
    if status:
        if status not in VALID_STATUSES:
            return jsonify({"error": f"status must be one of {VALID_STATUSES}"}), 400
        where.append("t.status = :status")
        params["status"] = status

    priority = request.args.get("priority")
    if priority:
        if priority not in VALID_PRIORITIES:
            return jsonify({"error": f"priority must be one of {VALID_PRIORITIES}"}), 400
        where.append("t.priority = :priority")
        params["priority"] = priority

    category_id = request.args.get("category_id", type=int)
    if category_id is not None:
        where.append("t.category_id = :category_id")
        params["category_id"] = category_id

    assigned_to = request.args.get("assigned_to", type=int)
    if assigned_to is not None:
        where.append("t.assigned_to = :assigned_to")
        params["assigned_to"] = assigned_to

    q = request.args.get("q")
    if q:
        where.append("(t.title LIKE :q OR t.description LIKE :q)")
        params["q"] = f"%{q}%"

    where_sql = " AND ".join(where) if where else "1=1"

    total = db.execute(
        f"SELECT COUNT(*) FROM tasks t WHERE {where_sql}", params
    ).fetchone()[0]
    offset = (page - 1) * per_page
    rows = db.execute(
        f"{_task_select()} WHERE {where_sql} ORDER BY t.id DESC LIMIT :per_page OFFSET :offset",
        {**params, "per_page": per_page, "offset": offset},
    ).fetchall()

    return (
        jsonify(
            {
                "items": [row_to_dict(r) for r in rows],
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "pages": (total + per_page - 1) // per_page,
                },
            }
        ),
        200,
    )


def _get_visible_task(task_id):
    db = get_db()
    row = db.execute(
        f"{_task_select()} WHERE t.id = :id AND (t.created_by = :uid OR t.assigned_to = :uid)",
        {"id": task_id, "uid": g.user["id"]},
    ).fetchone()
    return row


@tasks_bp.get("/<int:task_id>")
@auth_required
def get_task(task_id):
    row = _get_visible_task(task_id)
    if row is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify({"task": row_to_dict(row)}), 200


@tasks_bp.put("/<int:task_id>")
@auth_required
def update_task(task_id):
    db = get_db()
    existing = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?", (task_id, g.user["id"])
    ).fetchone()
    if existing is None:
        return jsonify({"error": "task not found or not owned by you"}), 403

    payload = request.get_json(silent=True) or {}

    title = payload.get("title", existing["title"])
    if not (title or "").strip():
        return jsonify({"error": "title is required"}), 400

    status = payload.get("status", existing["status"])
    priority = payload.get("priority", existing["priority"])
    if status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {VALID_STATUSES}"}), 400
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"priority must be one of {VALID_PRIORITIES}"}), 400

    description = payload.get("description", existing["description"])
    due_date = payload.get("due_date", existing["due_date"])
    category_id = _resolve_category(
        db, g.user["id"], payload.get("category_id", existing["category_id"])
    )
    if category_id is None and payload.get("category_id") is not None:
        return jsonify({"error": "category not found"}), 400

    assigned_to = payload.get("assigned_to", existing["assigned_to"])
    if assigned_to is not None:
        assignee = db.execute("SELECT id FROM users WHERE id = ?", (assigned_to,)).fetchone()
        if assignee is None:
            return jsonify({"error": "assigned_to user does not exist"}), 400

    db.execute(
        """UPDATE tasks SET title = ?, description = ?, status = ?, priority = ?,
              due_date = ?, category_id = ?, assigned_to = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (title.strip(), description, status, priority, due_date, category_id, assigned_to, task_id),
    )
    db.commit()
    task = db.execute(f"{_task_select()} WHERE t.id = ?", (task_id,)).fetchone()
    return jsonify({"task": row_to_dict(task)}), 200


@tasks_bp.post("/<int:task_id>/assign")
@auth_required
def assign_task(task_id):
    db = get_db()
    existing = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?", (task_id, g.user["id"])
    ).fetchone()
    if existing is None:
        return jsonify({"error": "task not found or not owned by you"}), 403

    payload = request.get_json(silent=True) or {}
    assigned_to = payload.get("assigned_to")
    if assigned_to is None:
        return jsonify({"error": "assigned_to is required"}), 400
    assignee = db.execute("SELECT id FROM users WHERE id = ?", (assigned_to,)).fetchone()
    if assignee is None:
        return jsonify({"error": "assigned_to user does not exist"}), 400

    db.execute(
        "UPDATE tasks SET assigned_to = ?, updated_at = datetime('now') WHERE id = ?",
        (assigned_to, task_id),
    )
    db.commit()
    task = db.execute(f"{_task_select()} WHERE t.id = ?", (task_id,)).fetchone()
    return jsonify({"task": row_to_dict(task)}), 200


@tasks_bp.delete("/<int:task_id>")
@auth_required
def delete_task(task_id):
    db = get_db()
    existing = db.execute(
        "SELECT * FROM tasks WHERE id = ? AND created_by = ?", (task_id, g.user["id"])
    ).fetchone()
    if existing is None:
        return jsonify({"error": "task not found or not owned by you"}), 403
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    return jsonify({"message": "task deleted"}), 200
