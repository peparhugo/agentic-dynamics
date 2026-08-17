from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from app.errors import APIError
from app.extensions import db
from app.models import TASK_PRIORITIES, TASK_STATUSES, Category, Task, User
from app.utils import (
    paginate_args,
    paginated_response,
    parse_iso_datetime,
    require_fields,
)

tasks_bp = Blueprint("tasks", __name__)


def _current_user_id():
    return int(get_jwt_identity())


def _get_visible_task_or_404(task_id, user_id):
    task = Task.query.get(task_id)
    if not task or (task.owner_id != user_id and task.assignee_id != user_id):
        raise APIError("Task not found", 404)
    return task


def _validate_category(category_id):
    if category_id is None:
        return None
    category = Category.query.get(category_id)
    if not category:
        raise APIError("category_id does not reference an existing category", 400)
    return category.id


def _validate_assignee(assignee_id):
    if assignee_id is None:
        return None
    user = User.query.get(assignee_id)
    if not user:
        raise APIError("assignee_id does not reference an existing user", 400)
    return user.id


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    user_id = _current_user_id()
    page, per_page = paginate_args()

    query = Task.query.filter(
        or_(Task.owner_id == user_id, Task.assignee_id == user_id)
    )

    status = request.args.get("status")
    if status:
        if status not in TASK_STATUSES:
            raise APIError(f"status must be one of {list(TASK_STATUSES)}", 400)
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        if priority not in TASK_PRIORITIES:
            raise APIError(f"priority must be one of {list(TASK_PRIORITIES)}", 400)
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id")
    if category_id:
        try:
            category_id = int(category_id)
        except ValueError:
            raise APIError("category_id must be an integer", 400)
        query = query.filter(Task.category_id == category_id)

    assignee_id = request.args.get("assignee_id")
    if assignee_id:
        try:
            assignee_id = int(assignee_id)
        except ValueError:
            raise APIError("assignee_id must be an integer", 400)
        query = query.filter(Task.assignee_id == assignee_id)

    search = request.args.get("q")
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    sort_by = request.args.get("sort_by", "created_at")
    sort_field_map = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "status": Task.status,
        "title": Task.title,
    }
    if sort_by not in sort_field_map:
        raise APIError(f"sort_by must be one of {list(sort_field_map)}", 400)
    order = request.args.get("order", "desc")
    if order not in ("asc", "desc"):
        raise APIError("order must be 'asc' or 'desc'", 400)
    field = sort_field_map[sort_by]
    query = query.order_by(field.asc() if order == "asc" else field.desc())

    return jsonify(paginated_response(query, page, per_page))


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    user_id = _current_user_id()
    task = _get_visible_task_or_404(task_id, user_id)
    return jsonify(task.to_dict())


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}
    require_fields(data, ["title"])

    status = data.get("status", "pending")
    if status not in TASK_STATUSES:
        raise APIError(f"status must be one of {list(TASK_STATUSES)}", 400)

    priority = data.get("priority", "medium")
    if priority not in TASK_PRIORITIES:
        raise APIError(f"priority must be one of {list(TASK_PRIORITIES)}", 400)

    category_id = _validate_category(data.get("category_id"))
    assignee_id = _validate_assignee(data.get("assignee_id"))
    due_date = parse_iso_datetime(data.get("due_date"))

    task = Task(
        title=data["title"].strip(),
        description=(data.get("description") or "").strip() or None,
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        assignee_id=assignee_id,
        owner_id=user_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    user_id = _current_user_id()
    task = _get_visible_task_or_404(task_id, user_id)

    data = request.get_json(silent=True) or {}
    is_owner = task.owner_id == user_id

    owner_only_fields = {"title", "description", "category_id", "assignee_id", "priority", "due_date"}
    if not is_owner:
        disallowed = owner_only_fields.intersection(data.keys())
        if disallowed:
            raise APIError(
                f"Only the task owner may update: {', '.join(sorted(disallowed))}",
                403,
            )

    if "title" in data:
        if not data["title"] or not data["title"].strip():
            raise APIError("title cannot be empty", 400)
        task.title = data["title"].strip()

    if "description" in data:
        task.description = (data["description"] or "").strip() or None

    if "status" in data:
        if data["status"] not in TASK_STATUSES:
            raise APIError(f"status must be one of {list(TASK_STATUSES)}", 400)
        task.status = data["status"]

    if "priority" in data:
        if data["priority"] not in TASK_PRIORITIES:
            raise APIError(f"priority must be one of {list(TASK_PRIORITIES)}", 400)
        task.priority = data["priority"]

    if "due_date" in data:
        task.due_date = parse_iso_datetime(data["due_date"])

    if "category_id" in data:
        task.category_id = _validate_category(data["category_id"])

    if "assignee_id" in data:
        task.assignee_id = _validate_assignee(data["assignee_id"])

    db.session.commit()
    return jsonify(task.to_dict())


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    user_id = _current_user_id()
    task = Task.query.get(task_id)
    if not task or task.owner_id != user_id:
        raise APIError("Task not found", 404)

    db.session.delete(task)
    db.session.commit()
    return "", 204


@tasks_bp.route("/<int:task_id>/assign", methods=["POST"])
@jwt_required()
def assign_task(task_id):
    user_id = _current_user_id()
    task = Task.query.get(task_id)
    if not task or task.owner_id != user_id:
        raise APIError("Task not found", 404)

    data = request.get_json(silent=True) or {}
    require_fields(data, ["assignee_id"])

    task.assignee_id = _validate_assignee(data["assignee_id"])
    db.session.commit()
    return jsonify(task.to_dict())
