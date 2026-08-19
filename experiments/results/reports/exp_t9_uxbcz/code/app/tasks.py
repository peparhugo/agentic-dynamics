from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models import Category, Task, User

task_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _parse_due_date(value):
    """Parse an ISO-8601 date/datetime string, returning a naive UTC datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("due_date must be a valid ISO-8601 datetime")
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _validate_task(data, partial=False):
    errors = []

    title = data.get("title")
    if not partial or "title" in data:
        if title is None or not str(title).strip():
            errors.append("title is required")

    status = data.get("status")
    if status is not None and status not in Task.STATUSES:
        errors.append(f"status must be one of {Task.STATUSES}")

    priority = data.get("priority")
    if priority is not None and priority not in Task.PRIORITIES:
        errors.append(f"priority must be one of {Task.PRIORITIES}")

    due_date = data.get("due_date")
    if "due_date" in data and due_date not in (None, ""):
        try:
            _parse_due_date(due_date)
        except ValueError as exc:
            errors.append(str(exc))

    return errors


def _task_to_dict(task):
    data = task.to_dict()
    data["category"] = task.category.name if task.category else None
    if task.assignee:
        data["assignee"] = {
            "id": task.assignee.id,
            "username": task.assignee.username,
        }
    else:
        data["assignee"] = None
    return data


@task_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    query = Task.query

    # Search across title and description
    q = request.args.get("q") or request.args.get("search")
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    # Filters
    status = request.args.get("status")
    if status:
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id", type=int)
    if category_id is not None:
        query = query.filter(Task.category_id == category_id)

    assignee_id = request.args.get("assignee_id", type=int)
    if assignee_id is not None:
        query = query.filter(Task.assignee_id == assignee_id)

    # Sorting
    sort = request.args.get("sort", "created_at")
    order = request.args.get("order", "desc")
    allowed_sort = {
        "id": Task.id,
        "title": Task.title,
        "status": Task.status,
        "priority": Task.priority,
        "due_date": Task.due_date,
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
    }
    sort_column = allowed_sort.get(sort, Task.created_at)
    query = query.order_by(
        sort_column.desc() if order == "desc" else sort_column.asc()
    )

    # Pagination
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", type=int) or current_app.config.get(
        "DEFAULT_PAGE_SIZE", 20
    )
    per_page = max(1, min(per_page, current_app.config.get("MAX_PAGE_SIZE", 100)))
    page = max(1, page)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tasks = [_task_to_dict(t) for t in pagination.items]

    return jsonify(
        {
            "tasks": tasks,
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        }
    ), 200


@task_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json(silent=True) or {}
    errors = _validate_task(data)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    title = str(data["title"]).strip()
    description = (data.get("description") or "").strip() or None
    status = data.get("status", Task.STATUS_TODO)
    priority = data.get("priority", Task.PRIORITY_MEDIUM)
    due_date = _parse_due_date(data.get("due_date"))

    category_id = data.get("category_id")
    if category_id is not None and db.session.get(Category, category_id) is None:
        return jsonify({"message": "category not found"}), 400

    assignee_id = data.get("assignee_id")
    if assignee_id is not None and db.session.get(User, assignee_id) is None:
        return jsonify({"message": "assignee not found"}), 400

    creator_id = int(get_jwt_identity())

    task = Task(
        title=title,
        description=description,
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        assignee_id=assignee_id,
        created_by_id=creator_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(_task_to_dict(task)), 201


@task_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"message": "task not found"}), 404
    return jsonify(_task_to_dict(task)), 200


@task_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"message": "task not found"}), 404

    data = request.get_json(silent=True) or {}
    errors = _validate_task(data, partial=True)
    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    if "title" in data and data["title"] is not None:
        task.title = str(data["title"]).strip()

    if "description" in data:
        task.description = (data.get("description") or "").strip() or None

    if "status" in data and data["status"] is not None:
        task.status = data["status"]

    if "priority" in data and data["priority"] is not None:
        task.priority = data["priority"]

    if "due_date" in data:
        task.due_date = _parse_due_date(data["due_date"])

    if "category_id" in data:
        category_id = data["category_id"]
        if category_id is not None and db.session.get(Category, category_id) is None:
            return jsonify({"message": "category not found"}), 400
        task.category_id = category_id

    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is not None and db.session.get(User, assignee_id) is None:
            return jsonify({"message": "assignee not found"}), 400
        task.assignee_id = assignee_id

    db.session.commit()
    return jsonify(_task_to_dict(task)), 200


@task_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"message": "task not found"}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "task deleted"}), 200
