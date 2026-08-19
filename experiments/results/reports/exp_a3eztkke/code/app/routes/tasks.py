from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import or_

from app.extensions import db
from app.models import Task, User
from app.utils import get_current_user, parse_datetime

tasks_bp = Blueprint("tasks", __name__)


def _split_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _validate_task_input(data, require_title=False):
    errors = {}

    title = data.get("title")
    if title is not None:
        title = str(title).strip()
        if not title:
            errors["title"] = "Title is required."
        elif len(title) > 200:
            errors["title"] = "Title must be 200 characters or fewer."
    elif require_title:
        errors["title"] = "Title is required."

    status = data.get("status")
    if status is not None:
        status = str(status).strip()
        if status not in Task.STATUSES:
            errors["status"] = f"Status must be one of: {', '.join(Task.STATUSES)}."

    priority = data.get("priority")
    if priority is not None:
        priority = str(priority).strip()
        if priority not in Task.PRIORITIES:
            errors["priority"] = f"Priority must be one of: {', '.join(Task.PRIORITIES)}."

    category = data.get("category")
    if category is not None:
        category = str(category).strip()
        if not category:
            errors["category"] = "Category cannot be empty."

    assigned_to = data.get("assigned_to")
    if assigned_to not in (None, ""):
        try:
            assigned_to = int(assigned_to)
        except (TypeError, ValueError):
            assigned_to = None
            errors["assigned_to"] = "assigned_to must be a valid user id."

    due_date = None
    if "due_date" in data:
        try:
            due_date = parse_datetime(data.get("due_date"))
        except ValueError as exc:
            errors["due_date"] = str(exc)

    return errors, title, status, priority, category, assigned_to, due_date


def _abort_if_forbidden(message="You do not have permission to perform this action."):
    return jsonify({"error": message}), 403


def _get_task_or_404(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return None
    return task


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "User not found."}), 401

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = max(1, min(per_page, 100))
    if page < 1:
        page = 1

    query = Task.query

    statuses = _split_list(request.args.get("status"))
    priorities = _split_list(request.args.get("priority"))
    categories = _split_list(request.args.get("category"))

    if statuses:
        query = query.filter(Task.status.in_(statuses))
    if priorities:
        query = query.filter(Task.priority.in_(priorities))
    if categories:
        query = query.filter(Task.category.in_(categories))

    assigned_to = request.args.get("assigned_to", type=int)
    if assigned_to is not None:
        query = query.filter(Task.assigned_to == assigned_to)

    created_by = request.args.get("created_by", type=int)
    if created_by is not None:
        query = query.filter(Task.created_by == created_by)

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Task.title.ilike(like), Task.description.ilike(like)))

    sort_field = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc").lower()
    sortable = {"title", "status", "priority", "category", "due_date", "created_at", "updated_at"}
    if sort_field not in sortable:
        sort_field = "created_at"
    column = getattr(Task, sort_field)
    query = query.order_by(column.desc() if order == "desc" else column.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "items": [task.to_dict() for task in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "User not found."}), 401

    data = request.get_json(silent=True) or {}
    errors, title, status, priority, category, assigned_to, due_date = _validate_task_input(
        data, require_title=True
    )
    if errors:
        return jsonify({"error": "Validation failed", "fields": errors}), 400

    if assigned_to is not None and db.session.get(User, assigned_to) is None:
        return jsonify({"error": "Assigned user does not exist."}), 400

    task = Task(
        title=title,
        description=(data.get("description") or ""),
        status=status if status is not None else "todo",
        priority=priority if priority is not None else "medium",
        category=category if category else Task.DEFAULT_CATEGORY,
        due_date=due_date,
        created_by=user.id,
        assigned_to=assigned_to,
    )
    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "User not found."}), 401

    task = _get_task_or_404(task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    return jsonify(task.to_dict()), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_task(task_id):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "User not found."}), 401

    task = _get_task_or_404(task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    if task.created_by != user.id and task.assigned_to != user.id:
        return _abort_if_forbidden()

    data = request.get_json(silent=True) or {}
    errors, title, status, priority, category, assigned_to, due_date = _validate_task_input(data)
    if errors:
        return jsonify({"error": "Validation failed", "fields": errors}), 400

    if assigned_to is not None and db.session.get(User, assigned_to) is None:
        return jsonify({"error": "Assigned user does not exist."}), 400

    if title:
        task.title = title
    if "description" in data:
        task.description = data.get("description") or ""
    if status is not None:
        task.status = status
    if priority is not None:
        task.priority = priority
    if "category" in data:
        task.category = category or Task.DEFAULT_CATEGORY
    if "due_date" in data:
        task.due_date = due_date
    if "assigned_to" in data:
        task.assigned_to = assigned_to

    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    user = get_current_user()
    if user is None:
        return jsonify({"error": "User not found."}), 401

    task = _get_task_or_404(task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    if task.created_by != user.id:
        return _abort_if_forbidden()

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted."}), 200
