from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from app.models import db, Task, User

tasks_bp = Blueprint("tasks", __name__)


def _get_current_user():
    user_id = get_jwt_identity()
    return db.session.get(User, int(user_id))


def _parse_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    user = _get_current_user()
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    status = data.get("status", "pending")
    if status not in Task.VALID_STATUSES:
        return jsonify({
            "error": f"Invalid status. Must be one of: {', '.join(sorted(Task.VALID_STATUSES))}"
        }), 400

    priority = data.get("priority", "medium")
    if priority not in Task.VALID_PRIORITIES:
        return jsonify({
            "error": f"Invalid priority. Must be one of: {', '.join(sorted(Task.VALID_PRIORITIES))}"
        }), 400

    due_date = None
    if data.get("due_date"):
        try:
            due_date = datetime.fromisoformat(data["due_date"])
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid due_date format. Use ISO 8601"}), 400

    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        if isinstance(assignee_id, str) and not assignee_id.strip():
            assignee_id = None
        else:
            try:
                assignee_id = int(assignee_id)
            except (ValueError, TypeError):
                return jsonify({"error": "assignee_id must be an integer"}), 400
            if not db.session.get(User, assignee_id):
                return jsonify({"error": "Assignee not found"}), 404

    task = Task(
        title=title,
        description=data.get("description", ""),
        status=status,
        priority=priority,
        category=data.get("category", "general"),
        due_date=due_date,
        creator_id=user.id,
        assignee_id=assignee_id,
    )
    db.session.add(task)
    db.session.commit()

    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    per_page = min(per_page, 100)

    query = Task.query

    status = request.args.get("status")
    if status:
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        query = query.filter(Task.priority == priority)

    category = request.args.get("category")
    if category:
        query = query.filter(Task.category == category)

    assignee_id = request.args.get("assignee_id", type=int)
    if assignee_id is not None:
        query = query.filter(Task.assignee_id == assignee_id)

    creator_id = request.args.get("creator_id", type=int)
    if creator_id is not None:
        query = query.filter(Task.creator_id == creator_id)

    search = request.args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Task.title.ilike(like),
                Task.description.ilike(like),
            )
        )

    due_before = request.args.get("due_before")
    if due_before:
        try:
            dt = datetime.fromisoformat(due_before)
            query = query.filter(Task.due_date <= dt)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid due_before format"}), 400

    due_after = request.args.get("due_after")
    if due_after:
        try:
            dt = datetime.fromisoformat(due_after)
            query = query.filter(Task.due_date >= dt)
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid due_after format"}), 400

    sort_by = request.args.get("sort_by", "created_at")
    sort_dir = request.args.get("sort_dir", "desc")
    sort_column = getattr(Task, sort_by, None)
    if sort_column is None:
        sort_column = Task.created_at
    if sort_dir == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "tasks": [t.to_dict() for t in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }), 200


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    user = _get_current_user()
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    if "title" in data:
        title = data["title"].strip()
        if not title:
            return jsonify({"error": "Title cannot be empty"}), 400
        task.title = title

    if "description" in data:
        task.description = data["description"]

    if "status" in data:
        status = data["status"]
        if status not in Task.VALID_STATUSES:
            return jsonify({
                "error": f"Invalid status. Must be one of: {', '.join(sorted(Task.VALID_STATUSES))}"
            }), 400
        task.status = status

    if "priority" in data:
        priority = data["priority"]
        if priority not in Task.VALID_PRIORITIES:
            return jsonify({
                "error": f"Invalid priority. Must be one of: {', '.join(sorted(Task.VALID_PRIORITIES))}"
            }), 400
        task.priority = priority

    if "category" in data:
        task.category = data["category"]

    if "due_date" in data:
        if data["due_date"] is None:
            task.due_date = None
        else:
            try:
                task.due_date = datetime.fromisoformat(data["due_date"])
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid due_date format"}), 400

    if "assignee_id" in data:
        aid = data["assignee_id"]
        if aid is None:
            task.assignee_id = None
        else:
            try:
                aid = int(aid)
            except (ValueError, TypeError):
                return jsonify({"error": "assignee_id must be an integer"}), 400
            if not db.session.get(User, aid):
                return jsonify({"error": "Assignee not found"}), 404
            task.assignee_id = aid

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200
