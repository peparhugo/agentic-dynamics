from datetime import datetime, timezone

from flask import Blueprint, request, g

from auth import login_required
from models import db, User, Task

tasks_bp = Blueprint("tasks", __name__)


def _parse_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return False


@tasks_bp.route("/api/tasks", methods=["POST"])
@login_required
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return {"error": "Request body must be JSON"}, 400

    title = (data.get("title") or "").strip()
    if not title:
        return {"error": "title is required"}, 400

    status = data.get("status", Task.STATUS_TODO)
    if status not in Task.VALID_STATUSES:
        return {
            "error": f"Invalid status. Must be one of: {', '.join(Task.VALID_STATUSES)}"
        }, 400

    priority = data.get("priority", Task.PRIORITY_MEDIUM)
    if priority not in Task.VALID_PRIORITIES:
        return {
            "error": f"Invalid priority. Must be one of: {', '.join(Task.VALID_PRIORITIES)}"
        }, 400

    category = (data.get("category") or "general").strip().lower()

    due_date = None
    due_date_str = data.get("due_date")
    if due_date_str:
        try:
            due_date = datetime.fromisoformat(due_date_str)
        except (ValueError, TypeError):
            return {"error": "Invalid due_date format. Use ISO 8601."}, 400

    assigned_to_id = data.get("assigned_to_id")
    if assigned_to_id is not None:
        assigned_user = db.session.get(User, assigned_to_id)
        if assigned_user is None:
            return {"error": "Assigned user not found"}, 404

    task = Task(
        title=title,
        description=data.get("description", ""),
        status=status,
        priority=priority,
        category=category,
        due_date=due_date,
        assigned_to_id=assigned_to_id,
        created_by_id=g.current_user.id,
    )
    db.session.add(task)
    db.session.commit()

    return {"task": task.to_dict()}, 201


@tasks_bp.route("/api/tasks", methods=["GET"])
@login_required
def list_tasks():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(max(per_page, 1), 100)

    query = Task.query

    status = request.args.get("status")
    if status:
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        query = query.filter(Task.priority == priority)

    category = request.args.get("category")
    if category:
        query = query.filter(Task.category == category)

    search = request.args.get("search")
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Task.title.ilike(pattern)) | (Task.description.ilike(pattern))
        )

    assigned_to = request.args.get("assigned_to", type=int)
    if assigned_to is not None:
        query = query.filter(Task.assigned_to_id == assigned_to)

    created_by = request.args.get("created_by", type=int)
    if created_by is not None:
        query = query.filter(Task.created_by_id == created_by)

    sort_by = request.args.get("sort_by", "created_at")
    sort_dir = request.args.get("sort_dir", "desc")
    valid_sort_fields = [
        "created_at", "updated_at", "due_date", "title", "status", "priority", "category"
    ]
    if sort_by in valid_sort_fields:
        col = getattr(Task, sort_by)
        query = query.order_by(col.desc() if sort_dir == "desc" else col.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return {
        "tasks": [t.to_dict() for t in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }, 200


@tasks_bp.route("/api/tasks/<int:task_id>", methods=["GET"])
@login_required
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return {"error": "Task not found"}, 404
    return {"task": task.to_dict()}, 200


@tasks_bp.route("/api/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return {"error": "Task not found"}, 404

    data = request.get_json(silent=True)
    if not data:
        return {"error": "Request body must be JSON"}, 400

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return {"error": "title cannot be empty"}, 400
        task.title = title

    if "description" in data:
        task.description = data["description"] or ""

    if "status" in data:
        status = data["status"]
        if status not in Task.VALID_STATUSES:
            return {
                "error": f"Invalid status. Must be one of: {', '.join(Task.VALID_STATUSES)}"
            }, 400
        task.status = status

    if "priority" in data:
        priority = data["priority"]
        if priority not in Task.VALID_PRIORITIES:
            return {
                "error": f"Invalid priority. Must be one of: {', '.join(Task.VALID_PRIORITIES)}"
            }, 400
        task.priority = priority

    if "category" in data:
        task.category = (data["category"] or "general").strip().lower()

    if "due_date" in data:
        due_date_str = data["due_date"]
        if due_date_str is None:
            task.due_date = None
        else:
            try:
                task.due_date = datetime.fromisoformat(due_date_str)
            except (ValueError, TypeError):
                return {"error": "Invalid due_date format. Use ISO 8601."}, 400

    if "assigned_to_id" in data:
        assigned_to_id = data["assigned_to_id"]
        if assigned_to_id is not None:
            assigned_user = db.session.get(User, assigned_to_id)
            if assigned_user is None:
                return {"error": "Assigned user not found"}, 404
        task.assigned_to_id = assigned_to_id

    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return {"task": task.to_dict()}, 200


@tasks_bp.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return {"error": "Task not found"}, 404

    db.session.delete(task)
    db.session.commit()

    return {"message": "Task deleted"}, 200
