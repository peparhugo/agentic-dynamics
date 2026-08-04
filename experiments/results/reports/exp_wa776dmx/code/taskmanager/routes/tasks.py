from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from ..models import db, Task, User, Category

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _parse_filters():
    filters = []
    status = request.args.get("status")
    priority = request.args.get("priority")
    category_id = request.args.get("category_id", type=int)
    due_before = request.args.get("due_before")
    due_after = request.args.get("due_after")
    search = request.args.get("search")
    owner_id = request.args.get("owner_id", type=int)
    assignee_id = request.args.get("assignee_id", type=int)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip() in Task.VALID_STATUSES]
        if statuses:
            filters.append(Task.status.in_(statuses))

    if priority:
        priorities = [p.strip() for p in priority.split(",") if p.strip() in Task.VALID_PRIORITIES]
        if priorities:
            filters.append(Task.priority.in_(priorities))

    if category_id:
        filters.append(Task.category_id == category_id)

    if due_before:
        try:
            dt = datetime.fromisoformat(due_before)
            filters.append(Task.due_date <= dt)
        except ValueError:
            pass

    if due_after:
        try:
            dt = datetime.fromisoformat(due_after)
            filters.append(Task.due_date >= dt)
        except ValueError:
            pass

    if search:
        search_term = f"%{search}%"
        filters.append(
            or_(Task.title.ilike(search_term), Task.description.ilike(search_term))
        )

    if owner_id:
        filters.append(Task.owner_id == owner_id)

    if assignee_id:
        filters.append(Task.assignees.any(User.id == assignee_id))

    return filters


@tasks_bp.route("", methods=["GET"])
def list_tasks():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")

    allowed_sort_fields = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "status": Task.status,
        "title": Task.title,
    }

    sort_column = allowed_sort_fields.get(sort_by, Task.created_at)
    if sort_order == "asc":
        sort_column = sort_column.asc()
    else:
        sort_column = sort_column.desc()

    query = Task.query
    for f in _parse_filters():
        query = query.filter(f)

    query = query.order_by(sort_column)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "tasks": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
    }), 200


@tasks_bp.route("/<int:task_id>", methods=["GET"])
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json()
    if "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    user_id = int(get_jwt_identity())

    status = data.get("status", "todo")
    if status not in Task.VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {Task.VALID_STATUSES}"}), 400

    priority = data.get("priority", "medium")
    if priority not in Task.VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {Task.VALID_PRIORITIES}"}), 400

    due_date = None
    if data.get("due_date"):
        try:
            due_date = datetime.fromisoformat(data["due_date"])
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid due_date format. Use ISO 8601."}), 400

    category_id = data.get("category_id")
    if category_id and not db.session.get(Category, category_id):
        return jsonify({"error": "Category not found"}), 400

    task = Task(
        title=data["title"],
        description=data.get("description"),
        status=status,
        priority=priority,
        due_date=due_date,
        owner_id=user_id,
        category_id=category_id,
    )

    assignee_ids = data.get("assignee_ids", [])
    if assignee_ids:
        users = User.query.filter(User.id.in_(assignee_ids)).all()
        if len(users) != len(assignee_ids):
            return jsonify({"error": "One or more assignee users not found"}), 400
        task.assignees.extend(users)

    db.session.add(task)
    db.session.commit()

    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    user_id = int(get_jwt_identity())
    if task.owner_id != user_id:
        return jsonify({"error": "You can only update your own tasks"}), 403

    data = request.get_json()

    if "title" in data:
        task.title = data["title"]
    if "description" in data:
        task.description = data["description"]
    if "status" in data:
        if data["status"] not in Task.VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {Task.VALID_STATUSES}"}), 400
        task.status = data["status"]
    if "priority" in data:
        if data["priority"] not in Task.VALID_PRIORITIES:
            return jsonify({"error": f"Invalid priority. Must be one of: {Task.VALID_PRIORITIES}"}), 400
        task.priority = data["priority"]
    if "due_date" in data:
        if data["due_date"] is None:
            task.due_date = None
        else:
            try:
                task.due_date = datetime.fromisoformat(data["due_date"])
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid due_date format. Use ISO 8601."}), 400
    if "category_id" in data:
        if data["category_id"] is None:
            task.category_id = None
        elif not db.session.get(Category, data["category_id"]):
            return jsonify({"error": "Category not found"}), 400
        else:
            task.category_id = data["category_id"]
    if "assignee_ids" in data:
        users = User.query.filter(User.id.in_(data["assignee_ids"])).all()
        if len(users) != len(data["assignee_ids"]):
            return jsonify({"error": "One or more assignee users not found"}), 400
        task.assignees = users

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    user_id = int(get_jwt_identity())
    if task.owner_id != user_id:
        return jsonify({"error": "You can only delete your own tasks"}), 403

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


@tasks_bp.route("/<int:task_id>/assign", methods=["POST"])
@jwt_required()
def assign_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    user_id = int(get_jwt_identity())
    if task.owner_id != user_id:
        return jsonify({"error": "Only the task owner can assign users"}), 403

    data = request.get_json()
    user_ids = data.get("user_ids", [])
    if not user_ids:
        return jsonify({"error": "user_ids list is required"}), 400

    users = User.query.filter(User.id.in_(user_ids)).all()
    if len(users) != len(user_ids):
        return jsonify({"error": "One or more users not found"}), 400

    task.assignees.extend(users)
    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>/unassign", methods=["POST"])
@jwt_required()
def unassign_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    user_id = int(get_jwt_identity())
    if task.owner_id != user_id:
        return jsonify({"error": "Only the task owner can unassign users"}), 403

    data = request.get_json()
    user_ids = data.get("user_ids", [])
    if not user_ids:
        return jsonify({"error": "user_ids list is required"}), 400

    users_to_remove = User.query.filter(User.id.in_(user_ids)).all()
    for u in users_to_remove:
        if u in task.assignees:
            task.assignees.remove(u)

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200
