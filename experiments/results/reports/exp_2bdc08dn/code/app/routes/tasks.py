from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import Category, Task, User

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api")

_DATE_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_due_date(raw):
    if not raw:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError("due_date must be in YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS format")


def _get_task_for_user(task_id, user_id):
    task = db.session.get(Task, task_id)
    if task is None or task.created_by != user_id:
        return None
    return task


def _validate_status_priority(data):
    status = data.get("status") or "todo"
    priority = data.get("priority") or "medium"
    if status not in Task.STATUSES:
        return None, None, {"error": f"status must be one of {Task.STATUSES}"}
    if priority not in Task.PRIORITIES:
        return None, None, {"error": f"priority must be one of {Task.PRIORITIES}"}
    return status, priority, None


def _resolve_category(category_id, user_id):
    category = db.session.get(Category, category_id)
    if category is None or category.user_id != user_id:
        return None, {"error": "category not found"}
    return category, None


def _resolve_assignee(assignee_id):
    assignee = db.session.get(User, assignee_id)
    if assignee is None:
        return None, {"error": "assignee not found"}
    return assignee, None


@tasks_bp.get("/tasks")
@jwt_required()
def list_tasks():
    user_id = int(get_jwt_identity())
    query = Task.query.filter_by(created_by=user_id)

    search = (request.args.get("search") or "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            Task.title.ilike(pattern) | Task.description.ilike(pattern)
        )

    status = request.args.get("status")
    if status:
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id", type=int)
    if category_id:
        query = query.filter(Task.category_id == category_id)

    assignee_id = request.args.get("assignee_id", type=int)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)

    query = query.order_by(Task.created_at.desc(), Task.id.desc())

    page = request.args.get("page", 1, type=int) or 1
    per_page = request.args.get("per_page", 10, type=int) or 10
    per_page = max(1, min(per_page, 100))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [task.to_dict() for task in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
        }
    )


@tasks_bp.post("/tasks")
@jwt_required()
def create_task():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    status, priority, error = _validate_status_priority(data)
    if error:
        return jsonify(error), 400

    try:
        due_date = parse_due_date(data.get("due_date"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    category = None
    if data.get("category_id") is not None:
        category, error = _resolve_category(data["category_id"], user_id)
        if error:
            return jsonify(error), 404

    assignee = None
    if data.get("assignee_id") is not None:
        assignee, error = _resolve_assignee(data["assignee_id"])
        if error:
            return jsonify(error), 404

    task = Task(
        title=title,
        description=data.get("description") or "",
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category.id if category else None,
        assignee_id=assignee.id if assignee else None,
        created_by=user_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.get("/tasks/<int:task_id>")
@jwt_required()
def get_task(task_id):
    user_id = int(get_jwt_identity())
    task = _get_task_for_user(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify({"task": task.to_dict()})


@tasks_bp.put("/tasks/<int:task_id>")
@jwt_required()
def update_task(task_id):
    user_id = int(get_jwt_identity())
    task = _get_task_for_user(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    status, priority, error = _validate_status_priority(data)
    if error:
        return jsonify(error), 400

    try:
        due_date = parse_due_date(data.get("due_date"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    category = None
    if data.get("category_id") is not None:
        category, error = _resolve_category(data["category_id"], user_id)
        if error:
            return jsonify(error), 404

    assignee = None
    if data.get("assignee_id") is not None:
        assignee, error = _resolve_assignee(data["assignee_id"])
        if error:
            return jsonify(error), 404

    task.title = title
    task.description = data.get("description") or ""
    task.status = status
    task.priority = priority
    task.due_date = due_date
    task.category_id = category.id if category else None
    task.assignee_id = assignee.id if assignee else None
    db.session.commit()
    return jsonify({"task": task.to_dict()})


@tasks_bp.patch("/tasks/<int:task_id>")
@jwt_required()
def partial_update_task(task_id):
    user_id = int(get_jwt_identity())
    task = _get_task_for_user(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        task.title = title

    if "description" in data:
        task.description = data.get("description") or ""

    if "status" in data:
        if data["status"] not in Task.STATUSES:
            return jsonify({"error": f"status must be one of {Task.STATUSES}"}), 400
        task.status = data["status"]

    if "priority" in data:
        if data["priority"] not in Task.PRIORITIES:
            return jsonify({"error": f"priority must be one of {Task.PRIORITIES}"}), 400
        task.priority = data["priority"]

    if "due_date" in data:
        try:
            task.due_date = parse_due_date(data.get("due_date"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    if "category_id" in data:
        if data["category_id"] is None:
            task.category_id = None
        else:
            category, error = _resolve_category(data["category_id"], user_id)
            if error:
                return jsonify(error), 404
            task.category_id = category.id

    if "assignee_id" in data:
        if data["assignee_id"] is None:
            task.assignee_id = None
        else:
            assignee, error = _resolve_assignee(data["assignee_id"])
            if error:
                return jsonify(error), 404
            task.assignee_id = assignee.id

    db.session.commit()
    return jsonify({"task": task.to_dict()})


@tasks_bp.delete("/tasks/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    user_id = int(get_jwt_identity())
    task = _get_task_for_user(task_id, user_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    db.session.delete(task)
    db.session.commit()
    return "", 204
