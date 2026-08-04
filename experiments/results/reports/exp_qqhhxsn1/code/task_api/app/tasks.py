from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from app.extensions import db
from app.models import Task, User

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


def _resolve_pagination():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", DEFAULT_PER_PAGE, type=int)
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = DEFAULT_PER_PAGE
    if per_page > MAX_PER_PAGE:
        per_page = MAX_PER_PAGE
    return page, per_page


def _get_user_or_404(user_id):
    user = db.session.get(User, user_id)
    if not user:
        from flask import abort

        abort(404, description="User not found")
    return user


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    status = data.get("status", "pending")
    priority = data.get("priority", "medium")
    category = data.get("category", "general") or "general"
    description = data.get("description") or ""
    assignee_id = data.get("assignee_id")

    if status not in Task.STATUS_CHOICES:
        return jsonify({"error": f"status must be one of {Task.STATUS_CHOICES}"}), 400
    if priority not in Task.PRIORITY_CHOICES:
        return jsonify({"error": f"priority must be one of {Task.PRIORITY_CHOICES}"}), 400

    due_date = None
    if data.get("due_date"):
        try:
            due_date = datetime.fromisoformat(data["due_date"])
        except (ValueError, TypeError):
            return jsonify({"error": "due_date must be ISO 8601 format"}), 400

    if assignee_id is not None:
        _get_user_or_404(assignee_id)

    owner_id = int(get_jwt_identity())
    task = Task(
        title=title,
        description=description,
        status=status,
        priority=priority,
        category=category.lower(),
        due_date=due_date,
        owner_id=owner_id,
        assignee_id=assignee_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    page, per_page = _resolve_pagination()

    query = Task.query

    status = request.args.get("status")
    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            query = query.filter(Task.status.in_(statuses))

    priority = request.args.get("priority")
    if priority:
        priorities = [p.strip() for p in priority.split(",") if p.strip()]
        if priorities:
            query = query.filter(Task.priority.in_(priorities))

    category = request.args.get("category")
    if category:
        categories = [c.strip().lower() for c in category.split(",") if c.strip()]
        if categories:
            query = query.filter(Task.category.in_(categories))

    owner_id = request.args.get("owner_id", type=int)
    if owner_id is not None:
        query = query.filter(Task.owner_id == owner_id)

    assignee_id = request.args.get("assignee_id", type=int)
    if assignee_id is not None:
        query = query.filter(Task.assignee_id == assignee_id)

    due_before = request.args.get("due_before")
    if due_before:
        try:
            dt = datetime.fromisoformat(due_before)
            query = query.filter(Task.due_date <= dt)
        except (ValueError, TypeError):
            return jsonify({"error": "due_before must be ISO 8601 format"}), 400

    due_after = request.args.get("due_after")
    if due_after:
        try:
            dt = datetime.fromisoformat(due_after)
            query = query.filter(Task.due_date >= dt)
        except (ValueError, TypeError):
            return jsonify({"error": "due_after must be ISO 8601 format"}), 400

    search = request.args.get("search")
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
        )

    sort_by = request.args.get("sort_by", "created_at")
    allowed_sorts = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "status": Task.status,
        "title": Task.title,
    }
    sort_col = allowed_sorts.get(sort_by, Task.created_at)

    sort_order = request.args.get("sort_order", "desc")
    if sort_order == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

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
    }), 200


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        task.title = title

    if "description" in data:
        task.description = data["description"] or ""

    if "status" in data:
        new_status = data["status"]
        if new_status not in Task.STATUS_CHOICES:
            return jsonify({"error": f"status must be one of {Task.STATUS_CHOICES}"}), 400
        try:
            task.transition(new_status)
        except ValueError as e:
            return jsonify({"error": str(e)}), 422

    if "priority" in data:
        priority = data["priority"]
        if priority not in Task.PRIORITY_CHOICES:
            return jsonify({"error": f"priority must be one of {Task.PRIORITY_CHOICES}"}), 400
        task.priority = priority

    if "category" in data:
        task.category = (data["category"] or "general").lower()

    if "due_date" in data:
        if data["due_date"] is None:
            task.due_date = None
        else:
            try:
                task.due_date = datetime.fromisoformat(data["due_date"])
            except (ValueError, TypeError):
                return jsonify({"error": "due_date must be ISO 8601 format"}), 400

    if "assignee_id" in data:
        if data["assignee_id"] is None:
            task.assignee_id = None
        else:
            _get_user_or_404(data["assignee_id"])
            task.assignee_id = data["assignee_id"]

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "task deleted"}), 200


@tasks_bp.route("/<int:task_id>/status", methods=["PATCH"])
@jwt_required()
def update_task_status(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True)
    if not data or "status" not in data:
        return jsonify({"error": "status field is required"}), 400

    new_status = data["status"]
    if new_status not in Task.STATUS_CHOICES:
        return jsonify({"error": f"status must be one of {Task.STATUS_CHOICES}"}), 400

    try:
        task.transition(new_status)
    except ValueError as e:
        return jsonify({"error": str(e)}), 422

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200
