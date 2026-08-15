from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from app.extensions import db
from app.models import TASK_PRIORITIES, TASK_STATUSES, Category, Task, User
from app.utils import error_response, paginate_query

tasks_bp = Blueprint("tasks", __name__)


def parse_due_date(value):
    if value in (None, ""):
        return None, None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")), None
    except (ValueError, AttributeError):
        return None, "due_date must be an ISO 8601 datetime string"


def get_owned_or_assigned_task(task_id, user_id):
    task = db.session.get(Task, task_id)
    if not task or (task.owner_id != user_id and task.assignee_id != user_id):
        return None
    return task


def validate_task_payload(data, partial=False):
    errors = {}
    title = data.get("title")

    if not partial or "title" in data:
        if not title or not str(title).strip():
            errors["title"] = "Title is required"

    if "status" in data and data["status"] not in TASK_STATUSES:
        errors["status"] = f"Status must be one of {TASK_STATUSES}"

    if "priority" in data and data["priority"] not in TASK_PRIORITIES:
        errors["priority"] = f"Priority must be one of {TASK_PRIORITIES}"

    return errors


@tasks_bp.post("")
@jwt_required()
def create_task():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    errors = validate_task_payload(data)

    due_date, due_date_error = parse_due_date(data.get("due_date"))
    if due_date_error:
        errors["due_date"] = due_date_error

    category_id = data.get("category_id")
    if category_id is not None:
        category = Category.query.filter_by(id=category_id, owner_id=user_id).first()
        if not category:
            errors["category_id"] = "Category not found"

    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        assignee = db.session.get(User, assignee_id)
        if not assignee:
            errors["assignee_id"] = "Assignee not found"

    if errors:
        return error_response("Validation failed", 422, errors)

    task = Task(
        title=data["title"].strip(),
        description=(data.get("description") or "").strip(),
        status=data.get("status", "todo"),
        priority=data.get("priority", "medium"),
        due_date=due_date,
        category_id=category_id,
        owner_id=user_id,
        assignee_id=assignee_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@tasks_bp.get("")
@jwt_required()
def list_tasks():
    user_id = int(get_jwt_identity())
    query = Task.query.filter(or_(Task.owner_id == user_id, Task.assignee_id == user_id))

    status = request.args.get("status")
    if status:
        if status not in TASK_STATUSES:
            return error_response("Invalid status filter", 400, {"status": f"Must be one of {TASK_STATUSES}"})
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        if priority not in TASK_PRIORITIES:
            return error_response(
                "Invalid priority filter", 400, {"priority": f"Must be one of {TASK_PRIORITIES}"}
            )
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id")
    if category_id:
        try:
            query = query.filter(Task.category_id == int(category_id))
        except ValueError:
            return error_response("category_id must be an integer", 400)

    assignee_id = request.args.get("assignee_id")
    if assignee_id:
        try:
            query = query.filter(Task.assignee_id == int(assignee_id))
        except ValueError:
            return error_response("assignee_id must be an integer", 400)

    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Task.title.ilike(like), Task.description.ilike(like)))

    sort_by = request.args.get("sort_by", "created_at")
    sort_dir = request.args.get("sort_dir", "desc")
    sort_column_map = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "title": Task.title,
    }
    sort_column = sort_column_map.get(sort_by, Task.created_at)
    query = query.order_by(sort_column.asc() if sort_dir == "asc" else sort_column.desc())

    result = paginate_query(query, lambda t: t.to_dict())
    return jsonify(result), 200


@tasks_bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id):
    user_id = int(get_jwt_identity())
    task = get_owned_or_assigned_task(task_id, user_id)
    if not task:
        return error_response("Task not found", 404)
    return jsonify(task.to_dict()), 200


@tasks_bp.put("/<int:task_id>")
@jwt_required()
def update_task(task_id):
    user_id = int(get_jwt_identity())
    task = get_owned_or_assigned_task(task_id, user_id)
    if not task:
        return error_response("Task not found", 404)

    data = request.get_json(silent=True) or {}

    is_owner = task.owner_id == user_id
    if not is_owner:
        disallowed = set(data.keys()) - {"status"}
        if disallowed:
            return error_response(
                "Assignees may only update the task status", 403, {"fields": sorted(disallowed)}
            )

    errors = validate_task_payload(data, partial=True)

    due_date = task.due_date
    if "due_date" in data:
        due_date, due_date_error = parse_due_date(data.get("due_date"))
        if due_date_error:
            errors["due_date"] = due_date_error

    if "category_id" in data and data["category_id"] is not None:
        category = Category.query.filter_by(id=data["category_id"], owner_id=task.owner_id).first()
        if not category:
            errors["category_id"] = "Category not found"

    if "assignee_id" in data and data["assignee_id"] is not None:
        assignee = db.session.get(User, data["assignee_id"])
        if not assignee:
            errors["assignee_id"] = "Assignee not found"

    if errors:
        return error_response("Validation failed", 422, errors)

    if "title" in data:
        task.title = data["title"].strip()
    if "description" in data:
        task.description = (data.get("description") or "").strip()
    if "status" in data:
        task.status = data["status"]
    if "priority" in data:
        task.priority = data["priority"]
    if "due_date" in data:
        task.due_date = due_date
    if "category_id" in data:
        task.category_id = data["category_id"]
    if "assignee_id" in data:
        task.assignee_id = data["assignee_id"]

    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    user_id = int(get_jwt_identity())
    task = Task.query.filter_by(id=task_id, owner_id=user_id).first()
    if not task:
        return error_response("Task not found", 404)

    db.session.delete(task)
    db.session.commit()
    return "", 204


@tasks_bp.post("/<int:task_id>/assign")
@jwt_required()
def assign_task(task_id):
    user_id = int(get_jwt_identity())
    task = Task.query.filter_by(id=task_id, owner_id=user_id).first()
    if not task:
        return error_response("Task not found", 404)

    data = request.get_json(silent=True) or {}
    assignee_id = data.get("assignee_id")
    username = data.get("username")

    if assignee_id is None and username:
        user = User.query.filter_by(username=username).first()
        assignee_id = user.id if user else None

    if assignee_id is None:
        return error_response(
            "assignee_id or username is required", 422, {"assignee_id": "This field is required"}
        )

    assignee = db.session.get(User, assignee_id)
    if not assignee:
        return error_response("Assignee not found", 404)

    task.assignee_id = assignee.id
    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.post("/<int:task_id>/unassign")
@jwt_required()
def unassign_task(task_id):
    user_id = int(get_jwt_identity())
    task = Task.query.filter_by(id=task_id, owner_id=user_id).first()
    if not task:
        return error_response("Task not found", 404)

    task.assignee_id = None
    db.session.commit()
    return jsonify(task.to_dict()), 200
