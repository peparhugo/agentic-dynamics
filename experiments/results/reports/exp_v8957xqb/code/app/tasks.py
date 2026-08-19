from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from .extensions import db
from .models import Task, User

tasks_bp = Blueprint("tasks", __name__)

MAX_PER_PAGE = 100
DEFAULT_PER_PAGE = 10


def _current_user_id():
    return int(get_jwt_identity())


def _parse_due_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        return datetime.strptime(value, "%Y-%m-%d").date()
    return value


def _get_user_or_404(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return None
    return user


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    query = Task.query

    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    assignee_id = request.args.get("assignee_id")
    search = request.args.get("q") or request.args.get("search")

    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if category:
        query = query.filter(Task.category == category)
    if assignee_id:
        query = query.filter(Task.assignee_id == int(assignee_id))
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Task.title.ilike(like), Task.description.ilike(like)))

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", DEFAULT_PER_PAGE, type=int)
    if page < 1:
        page = 1
    if per_page < 1 or per_page > MAX_PER_PAGE:
        per_page = DEFAULT_PER_PAGE

    pagination = query.order_by(Task.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

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
    data = request.get_json(silent=True) or {}

    if not data.get("title"):
        return jsonify({"error": "Validation Error", "message": "title is required"}), 400

    status = data.get("status", "pending")
    priority = data.get("priority", "medium")

    if status not in Task.STATUSES:
        return jsonify({"error": "Validation Error", "message": f"status must be one of {list(Task.STATUSES)}"}), 400
    if priority not in Task.PRIORITIES:
        return jsonify({"error": "Validation Error", "message": f"priority must be one of {list(Task.PRIORITIES)}"}), 400

    due_date = data.get("due_date")
    try:
        due_date = _parse_due_date(due_date)
    except ValueError:
        return jsonify({"error": "Validation Error", "message": "due_date must be in YYYY-MM-DD format"}), 400

    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        if not _get_user_or_404(assignee_id):
            return jsonify({"error": "Not Found", "message": "Assignee not found"}), 404
        assignee_id = int(assignee_id)

    task = Task(
        title=data["title"].strip(),
        description=data.get("description"),
        status=status,
        priority=priority,
        category=data.get("category"),
        due_date=due_date,
        creator_id=_current_user_id(),
        assignee_id=assignee_id,
    )
    db.session.add(task)
    db.session.commit()

    return jsonify(task.to_dict()), 201


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Not Found", "message": "Task not found"}), 404
    return jsonify(task.to_dict()), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Not Found", "message": "Task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        if not data.get("title"):
            return jsonify({"error": "Validation Error", "message": "title cannot be empty"}), 400
        task.title = data["title"].strip()

    if "description" in data:
        task.description = data.get("description")

    if "status" in data:
        status = data["status"]
        if status not in Task.STATUSES:
            return jsonify({"error": "Validation Error", "message": f"status must be one of {list(Task.STATUSES)}"}), 400
        task.status = status

    if "priority" in data:
        priority = data["priority"]
        if priority not in Task.PRIORITIES:
            return jsonify({"error": "Validation Error", "message": f"priority must be one of {list(Task.PRIORITIES)}"}), 400
        task.priority = priority

    if "category" in data:
        task.category = data.get("category")

    if "due_date" in data:
        try:
            task.due_date = _parse_due_date(data.get("due_date"))
        except ValueError:
            return jsonify({"error": "Validation Error", "message": "due_date must be in YYYY-MM-DD format"}), 400

    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is None:
            task.assignee_id = None
        else:
            if not _get_user_or_404(assignee_id):
                return jsonify({"error": "Not Found", "message": "Assignee not found"}), 404
            task.assignee_id = int(assignee_id)

    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Not Found", "message": "Task not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


@tasks_bp.route("/<int:task_id>/assign", methods=["POST"])
@jwt_required()
def assign_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Not Found", "message": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    assignee_id = data.get("assignee_id")
    if assignee_id is None:
        return jsonify({"error": "Validation Error", "message": "assignee_id is required"}), 400

    if not _get_user_or_404(assignee_id):
        return jsonify({"error": "Not Found", "message": "Assignee not found"}), 404

    task.assignee_id = int(assignee_id)
    db.session.commit()
    return jsonify(task.to_dict()), 200
