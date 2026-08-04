from datetime import datetime
from flask import Blueprint, request, jsonify, g
from auth_utils import login_required
from database import get_db
from config import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    description = (data.get("description") or "").strip()
    status = data.get("status", "pending")
    priority = data.get("priority", "medium")
    category_id = data.get("category_id")
    due_date = data.get("due_date")
    assigned_to = data.get("assigned_to")

    if status not in ("pending", "in_progress", "completed", "cancelled"):
        return jsonify({"error": "Invalid status"}), 400
    if priority not in ("low", "medium", "high", "urgent"):
        return jsonify({"error": "Invalid priority"}), 400

    if due_date:
        try:
            datetime.fromisoformat(due_date)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid due_date format, use ISO 8601"}), 400

    db = get_db()
    try:
        if category_id is not None:
            cat = db.execute(
                "SELECT id FROM categories WHERE id = ?", (category_id,)
            ).fetchone()
            if cat is None:
                db.close()
                return jsonify({"error": "Category not found"}), 404

        if assigned_to is not None:
            usr = db.execute(
                "SELECT id FROM users WHERE id = ?", (assigned_to,)
            ).fetchone()
            if usr is None:
                db.close()
                return jsonify({"error": "Assigned user not found"}), 404

        cursor = db.execute(
            """INSERT INTO tasks (title, description, status, priority, category_id, due_date, created_by, assigned_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, status, priority, category_id, due_date, g.current_user["id"], assigned_to),
        )
        db.commit()
        task_id = cursor.lastrowid
        task = _get_task_dict(db, task_id)
        db.close()
        return jsonify({"task": task}), 201
    except Exception:
        db.close()
        raise


@tasks_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", PAGE_SIZE_DEFAULT, type=int)
    per_page = min(per_page, PAGE_SIZE_MAX)
    offset = (page - 1) * per_page

    status = request.args.get("status")
    priority = request.args.get("priority")
    category_id = request.args.get("category_id", type=int)
    assigned_to = request.args.get("assigned_to", type=int)
    created_by = request.args.get("created_by", type=int)
    search = request.args.get("search")
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    due_before = request.args.get("due_before")
    due_after = request.args.get("due_after")

    allowed_sort = {
        "created_at", "updated_at", "due_date", "title", "status", "priority"
    }
    if sort_by not in allowed_sort:
        return jsonify({"error": f"Invalid sort_by, allowed: {', '.join(sorted(allowed_sort))}"}), 400
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    where_clauses = []
    params = []

    if status:
        where_clauses.append("t.status = ?")
        params.append(status)
    if priority:
        where_clauses.append("t.priority = ?")
        params.append(priority)
    if category_id is not None:
        where_clauses.append("t.category_id = ?")
        params.append(category_id)
    if assigned_to is not None:
        where_clauses.append("t.assigned_to = ?")
        params.append(assigned_to)
    if created_by is not None:
        where_clauses.append("t.created_by = ?")
        params.append(created_by)
    if search:
        where_clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if due_before:
        where_clauses.append("t.due_date <= ?")
        params.append(due_before)
    if due_after:
        where_clauses.append("t.due_date >= ?")
        params.append(due_after)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    order_col = f"t.{sort_by}" if sort_by in allowed_sort else "t.created_at"
    order_sql = f"ORDER BY {order_col} {sort_order}"

    db = get_db()

    count_row = db.execute(
        f"SELECT COUNT(*) FROM tasks t WHERE {where_sql}", params
    ).fetchone()
    total = count_row[0]

    rows = db.execute(
        f"""SELECT t.*, c.name AS category_name,
                   cu.username AS created_by_username,
                   au.username AS assigned_to_username
            FROM tasks t
            LEFT JOIN categories c ON t.category_id = c.id
            LEFT JOIN users cu ON t.created_by = cu.id
            LEFT JOIN users au ON t.assigned_to = au.id
            WHERE {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    ).fetchall()

    db.close()

    tasks = [_row_to_task(r) for r in rows]

    return jsonify({
        "tasks": tasks,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        },
    })


@tasks_bp.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def get_task(task_id):
    db = get_db()
    task = _get_task_dict(db, task_id)
    db.close()
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": task})


@tasks_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    db = get_db()
    existing = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if existing is None:
        db.close()
        return jsonify({"error": "Task not found"}), 404

    allowed = {"title", "description", "status", "priority", "category_id", "due_date", "assigned_to"}
    updates = {}
    for key in allowed:
        if key in data:
            updates[key] = data[key]

    if not updates:
        db.close()
        return jsonify({"error": "No valid fields to update"}), 400

    if "title" in updates and not (updates["title"] or "").strip():
        db.close()
        return jsonify({"error": "Title cannot be empty"}), 400

    if "status" in updates and updates["status"] not in ("pending", "in_progress", "completed", "cancelled"):
        db.close()
        return jsonify({"error": "Invalid status"}), 400

    if "priority" in updates and updates["priority"] not in ("low", "medium", "high", "urgent"):
        db.close()
        return jsonify({"error": "Invalid priority"}), 400

    if "due_date" in updates and updates["due_date"] is not None:
        try:
            datetime.fromisoformat(updates["due_date"])
        except (ValueError, TypeError):
            db.close()
            return jsonify({"error": "Invalid due_date format"}), 400

    if "category_id" in updates and updates["category_id"] is not None:
        cat = db.execute("SELECT id FROM categories WHERE id = ?", (updates["category_id"],)).fetchone()
        if cat is None:
            db.close()
            return jsonify({"error": "Category not found"}), 404

    if "assigned_to" in updates and updates["assigned_to"] is not None:
        usr = db.execute("SELECT id FROM users WHERE id = ?", (updates["assigned_to"],)).fetchone()
        if usr is None:
            db.close()
            return jsonify({"error": "Assigned user not found"}), 404

    set_clauses = []
    params = []
    for key, value in updates.items():
        set_clauses.append(f"{key} = ?")
        params.append(value)
    set_clauses.append("updated_at = datetime('now')")
    params.append(task_id)

    db.execute(
        f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?",
        params,
    )
    db.commit()

    task = _get_task_dict(db, task_id)
    db.close()
    return jsonify({"task": task})


@tasks_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    db = get_db()
    existing = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if existing is None:
        db.close()
        return jsonify({"error": "Task not found"}), 404

    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Task deleted"}), 200


@tasks_bp.route("/categories", methods=["GET"])
@login_required
def list_categories():
    db = get_db()
    rows = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    db.close()
    return jsonify({"categories": [dict(r) for r in rows]})


@tasks_bp.route("/categories", methods=["POST"])
@login_required
def create_category():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Category name is required"}), 400

    db = get_db()
    try:
        cursor = db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        db.commit()
        cat = db.execute("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,)).fetchone()
        db.close()
        return jsonify({"category": dict(cat)}), 201
    except Exception as e:
        db.close()
        if "unique" in str(e).lower():
            return jsonify({"error": "Category already exists"}), 409
        raise


def _get_task_dict(db, task_id):
    row = db.execute(
        """SELECT t.*, c.name AS category_name,
                  cu.username AS created_by_username,
                  au.username AS assigned_to_username
           FROM tasks t
           LEFT JOIN categories c ON t.category_id = c.id
           LEFT JOIN users cu ON t.created_by = cu.id
           LEFT JOIN users au ON t.assigned_to = au.id
           WHERE t.id = ?""",
        (task_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def _row_to_task(row):
    r = dict(row)
    r["category"] = {"id": r.pop("category_id"), "name": r.pop("category_name")} if r.get("category_name") else None
    r["created_by"] = {"id": r.pop("created_by"), "username": r.pop("created_by_username")}
    r["assigned_to"] = {"id": r.pop("assigned_to"), "username": r.pop("assigned_to_username")} if r.get("assigned_to_username") else None
    return r
