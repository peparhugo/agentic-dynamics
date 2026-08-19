from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import case, or_

from .extensions import db
from .models import Category, Task, User

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _parse_due_date(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return "invalid"


def _pagination_meta(pagination):
    return {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "total_pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    per_page = max(1, min(per_page, 100))
    page = max(1, page)

    query = Task.query

    status = request.args.get("status")
    if status:
        if status not in Task.STATUSES:
            return jsonify({"message": f"Invalid status. Allowed: {Task.STATUSES}"}), 400
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        if priority not in Task.PRIORITIES:
            return jsonify(
                {"message": f"Invalid priority. Allowed: {Task.PRIORITIES}"}
            ), 400
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id", type=int)
    if category_id:
        query = query.filter(Task.category_id == category_id)

    assignee_id = request.args.get("assignee_id", type=int)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    sort_by = request.args.get("sort_by", "created_at")
    priority_order = case(
        (Task.priority == "urgent", 3),
        (Task.priority == "high", 2),
        (Task.priority == "medium", 1),
        (Task.priority == "low", 0),
        else_=-1,
    )
    status_order = case(
        (Task.status == "in_progress", 2),
        (Task.status == "pending", 1),
        (Task.status == "completed", 0),
        else_=-1,
    )
    sort_columns = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": priority_order,
        "status": status_order,
    }
    if sort_by not in sort_columns:
        return jsonify({"message": f"Invalid sort_by. Allowed: {list(sort_columns)}"}), 400
    order = request.args.get("order", "desc")
    column = sort_columns[sort_by]
    query = query.order_by(column.desc() if order == "desc" else column.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "tasks": [t.to_dict() for t in pagination.items],
            "meta": _pagination_meta(pagination),
        }
    ), 200


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()

    if not title:
        return jsonify({"message": "Title is required."}), 400

    status = data.get("status", "pending")
    priority = data.get("priority", "medium")
    if status not in Task.STATUSES:
        return jsonify({"message": f"Invalid status. Allowed: {Task.STATUSES}"}), 400
    if priority not in Task.PRIORITIES:
        return jsonify(
            {"message": f"Invalid priority. Allowed: {Task.PRIORITIES}"}
        ), 400

    due_date = _parse_due_date(data.get("due_date"))
    if due_date == "invalid":
        return jsonify({"message": "Invalid due_date format. Use YYYY-MM-DD."}), 400

    category_id = data.get("category_id")
    if category_id is not None:
        if db.session.get(Category, category_id) is None:
            return jsonify({"message": "Category not found."}), 404

    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        if db.session.get(User, assignee_id) is None:
            return jsonify({"message": "Assignee not found."}), 404

    creator_id = int(get_jwt_identity())

    task = Task(
        title=title,
        description=data.get("description"),
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        assignee_id=assignee_id,
        creator_id=creator_id,
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"message": "Task not found."}), 404
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"message": "Task not found."}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"message": "Title is required."}), 400
        task.title = title

    if "description" in data:
        task.description = data.get("description")

    if "status" in data:
        status = data.get("status")
        if status not in Task.STATUSES:
            return jsonify({"message": f"Invalid status. Allowed: {Task.STATUSES}"}), 400
        task.status = status

    if "priority" in data:
        priority = data.get("priority")
        if priority not in Task.PRIORITIES:
            return jsonify(
                {"message": f"Invalid priority. Allowed: {Task.PRIORITIES}"}
            ), 400
        task.priority = priority

    if "due_date" in data:
        due_date = _parse_due_date(data.get("due_date"))
        if due_date == "invalid":
            return jsonify({"message": "Invalid due_date format. Use YYYY-MM-DD."}), 400
        task.due_date = due_date

    if "category_id" in data:
        category_id = data.get("category_id")
        if category_id is not None and db.session.get(Category, category_id) is None:
            return jsonify({"message": "Category not found."}), 404
        task.category_id = category_id

    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is not None and db.session.get(User, assignee_id) is None:
            return jsonify({"message": "Assignee not found."}), 404
        task.assignee_id = assignee_id

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"message": "Task not found."}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted."}), 200
