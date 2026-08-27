from flask import Blueprint, current_app, jsonify, request

from .extensions import db
from .models import Category, Task, User, VALID_PRIORITIES, VALID_STATUSES
from .utils import parse_datetime, token_required

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _apply_filters(query, args):
    status = args.get("status")
    if status:
        if status not in VALID_STATUSES:
            raise ValueError(
                f"invalid status, must be one of {', '.join(VALID_STATUSES)}"
            )
        query = query.filter(Task.status == status)

    priority = args.get("priority")
    if priority:
        if priority not in VALID_PRIORITIES:
            raise ValueError(
                f"invalid priority, must be one of {', '.join(VALID_PRIORITIES)}"
            )
        query = query.filter(Task.priority == priority)

    category_id = args.get("category_id")
    if category_id:
        query = query.filter(Task.category_id == int(category_id))

    category = args.get("category")
    if category:
        query = query.join(Category).filter(Category.name == category)

    assignee_id = args.get("assignee_id")
    if assignee_id:
        query = query.filter(Task.assignee_id == int(assignee_id))

    assignee = args.get("assignee")
    if assignee:
        query = query.join(User, User.id == Task.assignee_id).filter(
            User.username == assignee
        )

    search = args.get("search")
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    due_before = args.get("due_before")
    if due_before:
        query = query.filter(Task.due_date <= parse_datetime(due_before))

    due_after = args.get("due_after")
    if due_after:
        query = query.filter(Task.due_date >= parse_datetime(due_after))

    return query


def _paginate(query, args):
    default_per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    max_per_page = current_app.config["MAX_PAGE_SIZE"]

    try:
        page = max(int(args.get("page", 1)), 1)
    except (ValueError, TypeError):
        page = 1
    try:
        per_page = int(args.get("per_page", default_per_page))
    except (ValueError, TypeError):
        per_page = default_per_page

    per_page = max(1, min(per_page, max_per_page))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "tasks": [t.to_dict() for t in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


@tasks_bp.route("", methods=["POST"])
@token_required
def create_task(current_user):
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    status = data.get("status", "todo")
    priority = data.get("priority", "medium")
    if status not in VALID_STATUSES:
        return jsonify({"error": f"invalid status, must be one of {', '.join(VALID_STATUSES)}"}), 400
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"invalid priority, must be one of {', '.join(VALID_PRIORITIES)}"}), 400

    category_id = data.get("category_id")
    if category_id is not None and db.session.get(Category, category_id) is None:
        return jsonify({"error": "category not found"}), 404

    assignee_id = data.get("assignee_id")
    if assignee_id is not None and db.session.get(User, assignee_id) is None:
        return jsonify({"error": "assignee not found"}), 404

    due_date = parse_datetime(data.get("due_date"))
    if data.get("due_date") and due_date is None:
        return jsonify({"error": "invalid due_date format, use ISO 8601"}), 400

    task = Task(
        title=title,
        description=(data.get("description") or "").strip() or None,
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        assignee_id=assignee_id,
        creator_id=current_user.id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@tasks_bp.route("", methods=["GET"])
@token_required
def list_tasks(current_user):
    query = Task.query
    try:
        query = _apply_filters(query, request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    query = query.order_by(Task.created_at.desc())
    return jsonify(_paginate(query, request.args)), 200


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@token_required
def get_task(current_user, task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404
    return jsonify(task.to_dict()), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@token_required
def update_task(current_user, task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        task.title = title
    if "description" in data:
        task.description = (data.get("description") or "").strip() or None
    if "status" in data:
        status = data.get("status")
        if status not in VALID_STATUSES:
            return jsonify({"error": f"invalid status, must be one of {', '.join(VALID_STATUSES)}"}), 400
        task.status = status
    if "priority" in data:
        priority = data.get("priority")
        if priority not in VALID_PRIORITIES:
            return jsonify({"error": f"invalid priority, must be one of {', '.join(VALID_PRIORITIES)}"}), 400
        task.priority = priority
    if "due_date" in data:
        due_date = parse_datetime(data.get("due_date"))
        if data.get("due_date") and due_date is None:
            return jsonify({"error": "invalid due_date format, use ISO 8601"}), 400
        task.due_date = due_date
    if "category_id" in data:
        category_id = data.get("category_id")
        if category_id is not None and db.session.get(Category, category_id) is None:
            return jsonify({"error": "category not found"}), 404
        task.category_id = category_id
    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is not None and db.session.get(User, assignee_id) is None:
            return jsonify({"error": "assignee not found"}), 404
        task.assignee_id = assignee_id

    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@token_required
def delete_task(current_user, task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "task not found"}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "task deleted"}), 200
