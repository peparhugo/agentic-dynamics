from flask import Blueprint, request, jsonify, g, current_app

from taskapi.auth import login_required
from taskapi.database import query_one, query_all, execute, execute_returning, get_db

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api")

CATEGORIES_TABLE = "categories"
TASKS_TABLE = "tasks"

VALID_STATUSES = ("pending", "in_progress", "completed")
VALID_PRIORITIES = ("low", "medium", "high", "urgent")

TASK_COLUMNS = (
    "t.id", "t.title", "t.description", "t.status", "t.priority",
    "t.category_id", "c.name AS category_name",
    "t.assigned_to", "u.username AS assigned_username",
    "t.created_by", "t.due_date", "t.created_at", "t.updated_at",
)
TASK_SELECT = (
    "SELECT " + ", ".join(TASK_COLUMNS)
    + " FROM tasks t"
    + " LEFT JOIN categories c ON t.category_id = c.id"
    + " LEFT JOIN users u ON t.assigned_to = u.id"
)


def _task_row_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "priority": row["priority"],
        "category_id": row["category_id"],
        "category_name": row["category_name"],
        "assigned_to": row["assigned_to"],
        "assigned_username": row["assigned_username"],
        "created_by": row["created_by"],
        "due_date": row["due_date"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _category_row_to_dict(row):
    return {"id": row["id"], "name": row["name"], "description": row["description"]}


# ─── Categories ────────────────────────────────────────────────────────────

@tasks_bp.route("/categories", methods=["GET"])
@login_required
def list_categories():
    rows = query_all("SELECT id, name, description FROM categories ORDER BY name")
    return jsonify({"categories": [_category_row_to_dict(r) for r in rows]}), 200


@tasks_bp.route("/categories", methods=["POST"])
@login_required
def create_category():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()

    if not name:
        return jsonify({"error": "Category name is required"}), 422

    existing = query_one("SELECT id FROM categories WHERE name = ?", (name,))
    if existing:
        return jsonify({"error": "Category already exists"}), 409

    cat_id = execute_returning(
        "INSERT INTO categories (name, description) VALUES (?, ?)", (name, description)
    )
    row = query_one("SELECT id, name, description FROM categories WHERE id = ?", (cat_id,))
    return jsonify({"category": _category_row_to_dict(row)}), 201


@tasks_bp.route("/categories/<int:cat_id>", methods=["DELETE"])
@login_required
def delete_category(cat_id):
    row = query_one("SELECT id FROM categories WHERE id = ?", (cat_id,))
    if not row:
        return jsonify({"error": "Category not found"}), 404
    execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    return jsonify({"message": "Category deleted"}), 200


# ─── Tasks CRUD ────────────────────────────────────────────────────────────

def _build_task_filters():
    filters = []
    params = []

    status = request.args.get("status")
    if status:
        filters.append("t.status = ?")
        params.append(status)

    priority = request.args.get("priority")
    if priority:
        filters.append("t.priority = ?")
        params.append(priority)

    category_id = request.args.get("category_id")
    if category_id:
        filters.append("t.category_id = ?")
        params.append(int(category_id))

    assigned_to = request.args.get("assigned_to")
    if assigned_to:
        if assigned_to == "me":
            filters.append("t.assigned_to = ?")
            params.append(g.current_user["id"])
        elif assigned_to == "unassigned":
            filters.append("t.assigned_to IS NULL")
        else:
            filters.append("t.assigned_to = ?")
            params.append(int(assigned_to))

    created_by = request.args.get("created_by")
    if created_by:
        if created_by == "me":
            filters.append("t.created_by = ?")
            params.append(g.current_user["id"])
        else:
            filters.append("t.created_by = ?")
            params.append(int(created_by))

    search = request.args.get("search")
    if search:
        filters.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    due_before = request.args.get("due_before")
    if due_before:
        filters.append("t.due_date <= ?")
        params.append(due_before)

    due_after = request.args.get("due_after")
    if due_after:
        filters.append("t.due_date >= ?")
        params.append(due_after)

    where = " WHERE " + " AND ".join(filters) if filters else ""
    return where, params


@tasks_bp.route("/tasks", methods=["GET"])
@login_required
def list_tasks():
    where, params = _build_task_filters()

    page_size = current_app.config["PAGE_SIZE_DEFAULT"]
    try:
        ps = int(request.args.get("page_size", page_size))
        page_size = min(ps, current_app.config["PAGE_SIZE_MAX"])
        page_size = max(page_size, 1)
    except (ValueError, TypeError):
        pass

    page = 1
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (ValueError, TypeError):
        pass

    offset = (page - 1) * page_size

    sort_by = request.args.get("sort_by", "created_at")
    sort_dir = request.args.get("sort_dir", "desc").upper()
    allowed_sort = {
        "id", "title", "status", "priority", "due_date",
        "created_at", "updated_at", "category_id", "assigned_to",
    }
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    if sort_dir not in ("ASC", "DESC"):
        sort_dir = "DESC"

    with get_db() as conn:
        count_row = conn.execute(
            "SELECT COUNT(*) FROM tasks t" + where, params
        ).fetchone()
        total = count_row[0]

        rows = conn.execute(
            TASK_SELECT + where + f" ORDER BY t.{sort_by} {sort_dir} LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    return jsonify({
        "tasks": [_task_row_to_dict(r) for r in rows],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "pages": max((total + page_size - 1) // page_size, 1),
        },
    }), 200


@tasks_bp.route("/tasks/<int:task_id>", methods=["GET"])
@login_required
def get_task(task_id):
    row = query_one(TASK_SELECT + " WHERE t.id = ?", (task_id,))
    if not row:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": _task_row_to_dict(row)}), 200


@tasks_bp.route("/tasks", methods=["POST"])
@login_required
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 422

    description = data.get("description", "")
    status = data.get("status", "pending")
    priority = data.get("priority", "medium")
    category_id = data.get("category_id")
    assigned_to = data.get("assigned_to")
    due_date = data.get("due_date")
    created_by = g.current_user["id"]

    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"}), 422
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(VALID_PRIORITIES)}"}), 422

    if category_id is not None:
        cat = query_one("SELECT id FROM categories WHERE id = ?", (category_id,))
        if not cat:
            return jsonify({"error": "Category not found"}), 404

    if assigned_to is not None:
        user = query_one("SELECT id FROM users WHERE id = ?", (assigned_to,))
        if not user:
            return jsonify({"error": "Assigned user not found"}), 404

    task_id = execute_returning(
        "INSERT INTO tasks (title, description, status, priority, category_id, assigned_to, created_by, due_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, status, priority, category_id, assigned_to, created_by, due_date),
    )
    row = query_one(TASK_SELECT + " WHERE t.id = ?", (task_id,))
    return jsonify({"task": _task_row_to_dict(row)}), 201


@tasks_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    row = query_one("SELECT id, created_by FROM tasks WHERE id = ?", (task_id,))
    if not row:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    updates = {}
    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "Title cannot be empty"}), 422
        updates["title"] = title
    if "description" in data:
        updates["description"] = data["description"]
    if "status" in data:
        if data["status"] not in VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"}), 422
        updates["status"] = data["status"]
    if "priority" in data:
        if data["priority"] not in VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(VALID_PRIORITIES)}"}), 422
        updates["priority"] = data["priority"]
    if "category_id" in data:
        if data["category_id"] is not None:
            cat = query_one("SELECT id FROM categories WHERE id = ?", (data["category_id"],))
            if not cat:
                return jsonify({"error": "Category not found"}), 404
        updates["category_id"] = data["category_id"]
    if "assigned_to" in data:
        if data["assigned_to"] is not None:
            user = query_one("SELECT id FROM users WHERE id = ?", (data["assigned_to"],))
            if not user:
                return jsonify({"error": "Assigned user not found"}), 404
        updates["assigned_to"] = data["assigned_to"]
    if "due_date" in data:
        updates["due_date"] = data["due_date"]

    if not updates:
        return jsonify({"error": "No fields to update"}), 400

    updates["updated_at"] = None  # will use DEFAULT

    set_clauses = []
    params = []
    for k, v in updates.items():
        if k == "updated_at":
            set_clauses.append("updated_at = datetime('now')")
        else:
            set_clauses.append(f"{k} = ?")
            params.append(v)
    params.append(task_id)

    execute(f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?", params)
    row = query_one(TASK_SELECT + " WHERE t.id = ?", (task_id,))
    return jsonify({"task": _task_row_to_dict(row)}), 200


@tasks_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    row = query_one("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not row:
        return jsonify({"error": "Task not found"}), 404
    execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return jsonify({"message": "Task deleted"}), 200
