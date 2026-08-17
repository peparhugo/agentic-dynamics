from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from app.extensions import db
from app.models import Category, Task, TaskPriority, TaskStatus, User
from app.utils import get_pagination_args, paginated_response

tasks_bp = Blueprint("tasks", __name__)


def parse_due_date(value):
    if value in (None, ""):
        return None, None
    try:
        text = value.replace("Z", "+00:00") if isinstance(value, str) else value
        return datetime.fromisoformat(text), None
    except (TypeError, ValueError):
        return None, "due_date must be a valid ISO 8601 datetime string"


def validate_category(category_id, user_id):
    if category_id is None:
        return None, None
    category = Category.query.get(category_id)
    if category is None or category.owner_id != user_id:
        return None, "Invalid category_id"
    return category, None


def validate_assignee(assignee_id):
    if assignee_id is None:
        return None, None
    user = User.query.get(assignee_id)
    if user is None:
        return None, "Invalid assignee_id"
    return user, None


def can_view(task, user_id):
    return task.owner_id == user_id or task.assignee_id == user_id


def can_edit(task, user_id):
    return task.owner_id == user_id or task.assignee_id == user_id


@tasks_bp.post("")
@jwt_required()
def create_task():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    errors = {}
    if not title:
        errors["title"] = "Title is required"

    status = data.get("status", TaskStatus.PENDING)
    if status not in TaskStatus.ALL:
        errors["status"] = f"status must be one of {TaskStatus.ALL}"

    priority = data.get("priority", TaskPriority.MEDIUM)
    if priority not in TaskPriority.ALL:
        errors["priority"] = f"priority must be one of {TaskPriority.ALL}"

    due_date, due_date_error = parse_due_date(data.get("due_date"))
    if due_date_error:
        errors["due_date"] = due_date_error

    category_id = data.get("category_id")
    category, category_error = validate_category(category_id, user_id)
    if category_error:
        errors["category_id"] = category_error

    assignee_id = data.get("assignee_id")
    assignee, assignee_error = validate_assignee(assignee_id)
    if assignee_error:
        errors["assignee_id"] = assignee_error

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    task = Task(
        title=title,
        description=data.get("description"),
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category.id if category else None,
        owner_id=user_id,
        assignee_id=assignee.id if assignee else None,
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.get("")
@jwt_required()
def list_tasks():
    user_id = int(get_jwt_identity())
    page, per_page = get_pagination_args()

    query = Task.query.filter(
        or_(Task.owner_id == user_id, Task.assignee_id == user_id)
    )

    status = request.args.get("status")
    if status:
        if status not in TaskStatus.ALL:
            return (
                jsonify({"error": f"status must be one of {TaskStatus.ALL}"}),
                400,
            )
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        if priority not in TaskPriority.ALL:
            return (
                jsonify({"error": f"priority must be one of {TaskPriority.ALL}"}),
                400,
            )
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id")
    if category_id:
        try:
            query = query.filter(Task.category_id == int(category_id))
        except ValueError:
            return jsonify({"error": "category_id must be an integer"}), 400

    assignee_id = request.args.get("assignee_id")
    if assignee_id:
        try:
            query = query.filter(Task.assignee_id == int(assignee_id))
        except ValueError:
            return jsonify({"error": "assignee_id must be an integer"}), 400

    search = request.args.get("q") or request.args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    sort_by = request.args.get("sort_by", "created_at")
    sort_dir = request.args.get("sort_dir", "desc")
    sortable = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "status": Task.status,
        "title": Task.title,
    }
    column = sortable.get(sort_by, Task.created_at)
    query = query.order_by(column.desc() if sort_dir == "desc" else column.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(paginated_response(pagination)), 200


@tasks_bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id):
    user_id = int(get_jwt_identity())
    task = Task.query.get_or_404(task_id)
    if not can_view(task, user_id):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.put("/<int:task_id>")
@tasks_bp.patch("/<int:task_id>")
@jwt_required()
def update_task(task_id):
    user_id = int(get_jwt_identity())
    task = Task.query.get_or_404(task_id)
    if not can_edit(task, user_id):
        return jsonify({"error": "Forbidden"}), 403

    is_owner = task.owner_id == user_id
    data = request.get_json(silent=True) or {}
    errors = {}

    restricted_fields = {"title", "description", "priority", "due_date",
                          "category_id", "assignee_id"}
    if not is_owner and restricted_fields.intersection(data.keys()):
        return (
            jsonify(
                {
                    "error": "Only the task owner can update this field; "
                    "assignees may only update status"
                }
            ),
            403,
        )

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            errors["title"] = "Title cannot be empty"
        else:
            task.title = title

    if "description" in data:
        task.description = data.get("description")

    if "status" in data:
        status = data.get("status")
        if status not in TaskStatus.ALL:
            errors["status"] = f"status must be one of {TaskStatus.ALL}"
        else:
            task.status = status

    if "priority" in data:
        priority = data.get("priority")
        if priority not in TaskPriority.ALL:
            errors["priority"] = f"priority must be one of {TaskPriority.ALL}"
        else:
            task.priority = priority

    if "due_date" in data:
        due_date, due_date_error = parse_due_date(data.get("due_date"))
        if due_date_error:
            errors["due_date"] = due_date_error
        else:
            task.due_date = due_date

    if "category_id" in data:
        category, category_error = validate_category(data.get("category_id"), user_id)
        if category_error:
            errors["category_id"] = category_error
        else:
            task.category_id = category.id if category else None

    if "assignee_id" in data:
        assignee, assignee_error = validate_assignee(data.get("assignee_id"))
        if assignee_error:
            errors["assignee_id"] = assignee_error
        else:
            task.assignee_id = assignee.id if assignee else None

    if errors:
        db.session.rollback()
        return jsonify({"error": "Validation failed", "details": errors}), 400

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    user_id = int(get_jwt_identity())
    task = Task.query.get_or_404(task_id)
    if task.owner_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200
