from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import PRIORITY_VALUES, STATUS_VALUES, Category, Task, User
from app.utils import get_pagination_params, paginated_response

tasks_bp = Blueprint("tasks", __name__)


def parse_due_date(value):
    if not value:
        return None, None
    try:
        return datetime.fromisoformat(value), None
    except ValueError:
        return None, "due_date must be an ISO 8601 datetime string"


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    user = current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    status = data.get("status", "pending")
    if status not in STATUS_VALUES:
        return jsonify({"error": f"status must be one of {STATUS_VALUES}"}), 400

    priority = data.get("priority", "medium")
    if priority not in PRIORITY_VALUES:
        return jsonify({"error": f"priority must be one of {PRIORITY_VALUES}"}), 400

    due_date, err = parse_due_date(data.get("due_date"))
    if err:
        return jsonify({"error": err}), 400

    category_id = data.get("category_id")
    if category_id is not None:
        if not db.session.get(Category, category_id):
            return jsonify({"error": "category not found"}), 404

    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        if not db.session.get(User, assignee_id):
            return jsonify({"error": "assignee not found"}), 404
    else:
        assignee_id = user.id

    task = Task(
        title=title,
        description=data.get("description"),
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        assignee_id=assignee_id,
        owner_id=user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    page, per_page = get_pagination_params()

    query = Task.query

    status = request.args.get("status")
    if status:
        if status not in STATUS_VALUES:
            return jsonify({"error": f"status must be one of {STATUS_VALUES}"}), 400
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        if priority not in PRIORITY_VALUES:
            return jsonify({"error": f"priority must be one of {PRIORITY_VALUES}"}), 400
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id")
    if category_id:
        query = query.filter(Task.category_id == category_id)

    assignee_id = request.args.get("assignee_id")
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)

    owner_id = request.args.get("owner_id")
    if owner_id:
        query = query.filter(Task.owner_id == owner_id)

    search = request.args.get("q")
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(Task.title.ilike(like), Task.description.ilike(like)))

    query = query.order_by(Task.created_at.desc())

    result = paginated_response(query, page, per_page, lambda t: t.to_dict())
    return jsonify(result), 200


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify({"task": task.to_dict()}), 200


def _authorize_mutation(task, user):
    return task.owner_id == user.id or task.assignee_id == user.id


@tasks_bp.route("/<int:task_id>", methods=["PUT", "PATCH"])
@jwt_required()
def update_task(task_id):
    user = current_user()
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    if not _authorize_mutation(task, user):
        return jsonify({"error": "not authorized to modify this task"}), 403

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        task.title = title

    if "description" in data:
        task.description = data.get("description")

    if "status" in data:
        status = data.get("status")
        if status not in STATUS_VALUES:
            return jsonify({"error": f"status must be one of {STATUS_VALUES}"}), 400
        task.status = status

    if "priority" in data:
        priority = data.get("priority")
        if priority not in PRIORITY_VALUES:
            return jsonify({"error": f"priority must be one of {PRIORITY_VALUES}"}), 400
        task.priority = priority

    if "due_date" in data:
        due_date, err = parse_due_date(data.get("due_date"))
        if err:
            return jsonify({"error": err}), 400
        task.due_date = due_date

    if "category_id" in data:
        category_id = data.get("category_id")
        if category_id is not None and not db.session.get(Category, category_id):
            return jsonify({"error": "category not found"}), 404
        task.category_id = category_id

    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is not None and not db.session.get(User, assignee_id):
            return jsonify({"error": "assignee not found"}), 404
        task.assignee_id = assignee_id

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    user = current_user()
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    if task.owner_id != user.id:
        return jsonify({"error": "only the owner can delete this task"}), 403

    db.session.delete(task)
    db.session.commit()
    return "", 204
