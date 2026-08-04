from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import db, Task, User, TaskStatus, TaskPriority

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _validate_task_data(data, partial=False):
    errors = {}
    if not partial or "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            errors["title"] = "Title is required."
    if "status" in data:
        status_val = data.get("status")
        if status_val and status_val not in [s.value for s in TaskStatus]:
            errors["status"] = f"Invalid status. Must be one of: {[s.value for s in TaskStatus]}"
    if "priority" in data:
        priority_val = data.get("priority")
        if priority_val and priority_val not in [p.value for p in TaskPriority]:
            errors["priority"] = f"Invalid priority. Must be one of: {[p.value for p in TaskPriority]}"
    if "assigned_to" in data:
        assigned_to = data.get("assigned_to")
        if assigned_to is not None:
            if not isinstance(assigned_to, int) and not (isinstance(assigned_to, str) and assigned_to.isdigit()):
                errors["assigned_to"] = "Must be a user ID."
            elif db.session.get(User, int(assigned_to)) is None:
                errors["assigned_to"] = "User not found."
    if "due_date" in data:
        due = data.get("due_date")
        if due is not None:
            parsed = _parse_date(due)
            if parsed is None:
                errors["due_date"] = "Invalid ISO 8601 date format."
    return errors


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(max(per_page, 1), 100)

    query = Task.query

    status_filter = request.args.get("status")
    if status_filter:
        query = query.filter(Task.status == status_filter)

    priority_filter = request.args.get("priority")
    if priority_filter:
        query = query.filter(Task.priority == priority_filter)

    category_filter = request.args.get("category")
    if category_filter:
        query = query.filter(Task.category == category_filter)

    assigned_to_filter = request.args.get("assigned_to", type=int)
    if assigned_to_filter is not None:
        query = query.filter(Task.assigned_to == assigned_to_filter)

    search = request.args.get("search")
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            db.or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
        )

    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")
    sort_columns = {
        "id": Task.id,
        "title": Task.title,
        "status": Task.status,
        "priority": Task.priority,
        "category": Task.category,
        "due_date": Task.due_date,
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
    }
    column = sort_columns.get(sort_by, Task.created_at)
    if sort_order == "asc":
        query = query.order_by(column.asc())
    else:
        query = query.order_by(column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "tasks": [t.to_dict() for t in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    })


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json(silent=True) or {}
    errors = _validate_task_data(data)
    if errors:
        return jsonify({"errors": errors}), 400

    current_user_id = int(get_jwt_identity())

    task = Task(
        title=data["title"].strip(),
        description=data.get("description", ""),
        status=data.get("status", TaskStatus.TODO.value),
        priority=data.get("priority", TaskPriority.MEDIUM.value),
        category=data.get("category", "general"),
        due_date=_parse_date(data.get("due_date")),
        created_by=current_user_id,
        assigned_to=data.get("assigned_to"),
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    return jsonify({"task": task.to_dict()})


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    data = request.get_json(silent=True) or {}
    errors = _validate_task_data(data, partial=True)
    if errors:
        return jsonify({"errors": errors}), 400

    if "title" in data:
        task.title = data["title"].strip()
    if "description" in data:
        task.description = data["description"]
    if "status" in data:
        task.status = data["status"]
    if "priority" in data:
        task.priority = data["priority"]
    if "category" in data:
        task.category = data["category"]
    if "due_date" in data:
        task.due_date = _parse_date(data["due_date"])
    if "assigned_to" in data:
        task.assigned_to = data["assigned_to"]

    db.session.commit()
    return jsonify({"task": task.to_dict()})


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted."}), 200
