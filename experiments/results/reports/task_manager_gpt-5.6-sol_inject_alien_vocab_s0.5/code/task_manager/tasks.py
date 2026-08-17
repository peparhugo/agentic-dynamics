from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import or_

from task_manager import db
from task_manager.models import Category, Task, User
from task_manager.utils import (
    current_user,
    json_body,
    json_error,
    parse_due_date,
    positive_int_arg,
)


tasks_bp = Blueprint("tasks", __name__)
STATUSES = {"pending", "in_progress", "completed"}
PRIORITIES = {"low", "medium", "high", "urgent"}


def validate_relation(model, value, field):
    if value is None:
        return None, None
    if isinstance(value, bool) or not isinstance(value, int):
        return None, f"{field} must be an integer or null"
    record = db.session.get(model, value)
    if not record:
        return None, f"{field} does not reference an existing record"
    return record, None


def apply_fields(task, data, creating=False):
    if creating or "title" in data:
        title = data.get("title", "")
        if not isinstance(title, str) or not title.strip():
            return "title is required"
        if len(title.strip()) > 200:
            return "title must not exceed 200 characters"
        task.title = title.strip()
    if "description" in data:
        if data["description"] is not None and not isinstance(data["description"], str):
            return "description must be a string or null"
        task.description = data["description"]
    if "status" in data:
        if data["status"] not in STATUSES:
            return f"status must be one of: {', '.join(sorted(STATUSES))}"
        task.status = data["status"]
    if "priority" in data:
        if data["priority"] not in PRIORITIES:
            return f"priority must be one of: {', '.join(sorted(PRIORITIES))}"
        task.priority = data["priority"]
    if "due_date" in data:
        try:
            task.due_date = parse_due_date(data["due_date"])
        except ValueError as exc:
            return str(exc)
    if "category_id" in data:
        category, error = validate_relation(Category, data["category_id"], "category_id")
        if error:
            return error
        task.category = category
    if "assignee_id" in data:
        assignee, error = validate_relation(User, data["assignee_id"], "assignee_id")
        if error:
            return error
        task.assignee = assignee
    return None


def visible_task_or_404(task_id, user):
    task = db.session.get(Task, task_id)
    if not task or user.id not in (task.creator_id, task.assignee_id):
        return None
    return task


@tasks_bp.post("")
@jwt_required()
def create_task():
    data = json_body()
    if not isinstance(data, dict):
        return json_error("A JSON object is required")
    user = current_user()
    task = Task(creator=user)
    error = apply_fields(task, data, creating=True)
    if error:
        return json_error(error)
    db.session.add(task)
    db.session.commit()
    return jsonify(task=task.to_dict()), 201


@tasks_bp.get("")
@jwt_required()
def list_tasks():
    user = current_user()
    try:
        page = positive_int_arg("page", 1)
        per_page = positive_int_arg("per_page", 20, maximum=100)
    except ValueError as exc:
        return json_error(str(exc))

    query = Task.query.filter(or_(Task.creator_id == user.id, Task.assignee_id == user.id))
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category") or request.args.get("category_id")
    search = request.args.get("search", "").strip()
    if status:
        if status not in STATUSES:
            return json_error("Invalid status filter")
        query = query.filter(Task.status == status)
    if priority:
        if priority not in PRIORITIES:
            return json_error("Invalid priority filter")
        query = query.filter(Task.priority == priority)
    if category:
        try:
            category_id = int(category)
            query = query.filter(Task.category_id == category_id)
        except ValueError:
            query = query.join(Category).filter(db.func.lower(Category.name) == category.lower())
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))

    pagination = query.order_by(Task.created_at.desc(), Task.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify(
        tasks=[task.to_dict() for task in pagination.items],
        pagination={
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    )


@tasks_bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id):
    task = visible_task_or_404(task_id, current_user())
    if not task:
        return json_error("Task not found", 404)
    return jsonify(task=task.to_dict())


@tasks_bp.patch("/<int:task_id>")
@jwt_required()
def update_task(task_id):
    user = current_user()
    task = visible_task_or_404(task_id, user)
    if not task:
        return json_error("Task not found", 404)
    if task.creator_id != user.id:
        return json_error("Only the task creator may update this task", 403)
    data = json_body()
    if not isinstance(data, dict):
        return json_error("A JSON object is required")
    error = apply_fields(task, data)
    if error:
        return json_error(error)
    db.session.commit()
    return jsonify(task=task.to_dict())


@tasks_bp.put("/<int:task_id>")
@jwt_required()
def replace_task(task_id):
    return update_task(task_id)


@tasks_bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    user = current_user()
    task = visible_task_or_404(task_id, user)
    if not task:
        return json_error("Task not found", 404)
    if task.creator_id != user.id:
        return json_error("Only the task creator may delete this task", 403)
    db.session.delete(task)
    db.session.commit()
    return "", 204
