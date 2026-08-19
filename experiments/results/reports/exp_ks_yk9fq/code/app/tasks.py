from datetime import datetime

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Category, Task, User
from app.utils import token_required

tasks_bp = Blueprint("tasks", __name__)

ALLOWED_STATUSES = set(Task.STATUSES)
ALLOWED_PRIORITIES = set(Task.PRIORITIES)
ALLOWED_SORT_FIELDS = {"created_at", "updated_at", "due_date", "priority", "status", "title"}
ALLOWED_ORDER = {"asc", "desc"}


def _parse_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_date(value):
    if value is None or value == "":
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid date '{value}', expected YYYY-MM-DD")


def _validate_task_payload(data):
    errors = {}
    title = (data.get("title") or "").strip()
    if not title:
        errors["title"] = "Title is required"

    status = data.get("status", "todo")
    if status not in ALLOWED_STATUSES:
        errors["status"] = f"Status must be one of {sorted(ALLOWED_STATUSES)}"

    priority = data.get("priority", "medium")
    if priority not in ALLOWED_PRIORITIES:
        errors["priority"] = f"Priority must be one of {sorted(ALLOWED_PRIORITIES)}"

    category_id = data.get("category_id")
    if category_id is not None:
        category = db.session.get(Category, category_id)
        if category is None:
            errors["category_id"] = "Category does not exist"

    assignee_id = data.get("assignee_id")
    if assignee_id is not None:
        user = db.session.get(User, assignee_id)
        if user is None:
            errors["assignee_id"] = "Assignee does not exist"

    due_date = None
    if "due_date" in data and data.get("due_date") not in (None, ""):
        try:
            due_date = _parse_date(data.get("due_date"))
        except ValueError as exc:
            errors["due_date"] = str(exc)

    return errors, title, status, priority, category_id, assignee_id, due_date


def _paginated_response(query, page, per_page):
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "tasks": [t.to_dict() for t in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }
    ), 200


@tasks_bp.route("/tasks", methods=["GET"])
@token_required
def list_tasks():
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        per_page = max(int(request.args.get("per_page", 10)), 1)
    except ValueError:
        per_page = 10
    per_page = min(per_page, 100)

    query = Task.query

    status = request.args.get("status")
    if status:
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id")
    if category_id:
        query = query.filter(Task.category_id == int(category_id))

    assignee_id = request.args.get("assignee_id")
    if assignee_id:
        query = query.filter(Task.assignee_id == int(assignee_id))

    creator_id = request.args.get("creator_id")
    if creator_id:
        query = query.filter(Task.creator_id == int(creator_id))

    q = request.args.get("q")
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Task.title.ilike(like)) | (Task.description.ilike(like))
        )

    if request.args.get("due_from"):
        try:
            query = query.filter(Task.due_date >= _parse_date(request.args.get("due_from")))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    if request.args.get("due_to"):
        try:
            query = query.filter(Task.due_date <= _parse_date(request.args.get("due_to")))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    sort_by = request.args.get("sort_by", "created_at")
    order = request.args.get("order", "desc")

    if sort_by not in ALLOWED_SORT_FIELDS:
        return jsonify({"error": f"Invalid sort_by, must be one of {sorted(ALLOWED_SORT_FIELDS)}"}), 400
    if order not in ALLOWED_ORDER:
        return jsonify({"error": f"Invalid order, must be one of {sorted(ALLOWED_ORDER)}"}), 400

    sort_column = getattr(Task, sort_by)
    if order == "desc":
        sort_column = sort_column.desc()
    else:
        sort_column = sort_column.asc()

    query = query.order_by(sort_column, Task.id.desc())
    return _paginated_response(query, page, per_page)


@tasks_bp.route("/tasks", methods=["POST"])
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    errors, title, status, priority, category_id, assignee_id, due_date = _validate_task_payload(data)

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    task = Task(
        title=title,
        description=data.get("description"),
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        creator_id=request.current_user.id,
        assignee_id=assignee_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"message": "Task created", "task": task.to_dict()}), 201


@tasks_bp.route("/tasks/<int:task_id>", methods=["GET"])
@token_required
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/tasks/<int:task_id>", methods=["PUT"])
@token_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    errors, title, status, priority, category_id, assignee_id, due_date = _validate_task_payload(data)

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    task.title = title
    task.status = status
    task.priority = priority
    task.category_id = category_id
    task.assignee_id = assignee_id
    if "due_date" in data:
        task.due_date = due_date
    if "description" in data:
        task.description = data.get("description")

    db.session.commit()
    return jsonify({"message": "Task updated", "task": task.to_dict()}), 200


@tasks_bp.route("/tasks/<int:task_id>", methods=["DELETE"])
@token_required
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200
