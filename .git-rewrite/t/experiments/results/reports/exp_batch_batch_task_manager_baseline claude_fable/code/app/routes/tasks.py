"""Task CRUD, assignment, pagination, search and filtering."""
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from app import db
from app.models import VALID_PRIORITIES, VALID_STATUSES, Category, Task, User

tasks_bp = Blueprint("tasks", __name__)

MAX_PER_PAGE = 100


def _current_user_id() -> int:
    return int(get_jwt_identity())


def _parse_due_date(value):
    """Parse ISO-8601 due date. Returns (datetime|None, error|None)."""
    if value is None or value == "":
        return None, None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")), None
    except (ValueError, TypeError):
        return None, "due_date must be a valid ISO-8601 datetime"


def _validate_category(category_id, user_id):
    """Returns (category_id|None, error|None)."""
    if category_id is None:
        return None, None
    category = Category.query.filter_by(id=category_id, user_id=user_id).first()
    if not category:
        return None, "Category not found"
    return category.id, None


def _validate_assignee(assignee_id):
    """Returns (assignee_id|None, error|None)."""
    if assignee_id is None:
        return None, None
    user = db.session.get(User, assignee_id)
    if not user:
        return None, "Assignee not found"
    return user.id, None


def _visible_tasks_query(user_id):
    """Tasks the user created or is assigned to."""
    return Task.query.filter(
        or_(Task.creator_id == user_id, Task.assignee_id == user_id))


@tasks_bp.post("")
@jwt_required()
def create_task():
    user_id = _current_user_id()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    if len(title) > 200:
        return jsonify({"error": "title must be at most 200 characters"}), 400

    status = data.get("status", "todo")
    if status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {list(VALID_STATUSES)}"}), 400

    priority = data.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        return jsonify(
            {"error": f"priority must be one of {list(VALID_PRIORITIES)}"}), 400

    due_date, err = _parse_due_date(data.get("due_date"))
    if err:
        return jsonify({"error": err}), 400

    category_id, err = _validate_category(data.get("category_id"), user_id)
    if err:
        return jsonify({"error": err}), 404

    assignee_id, err = _validate_assignee(data.get("assignee_id"))
    if err:
        return jsonify({"error": err}), 404

    task = Task(
        title=title,
        description=(data.get("description") or "").strip(),
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        creator_id=user_id,
        assignee_id=assignee_id,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"task": task.to_dict()}), 201


@tasks_bp.get("")
@jwt_required()
def list_tasks():
    user_id = _current_user_id()
    query = _visible_tasks_query(user_id)

    # --- Filters ---
    status = request.args.get("status")
    if status:
        if status not in VALID_STATUSES:
            return jsonify(
                {"error": f"status must be one of {list(VALID_STATUSES)}"}), 400
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        if priority not in VALID_PRIORITIES:
            return jsonify(
                {"error": f"priority must be one of {list(VALID_PRIORITIES)}"}), 400
        query = query.filter(Task.priority == priority)

    category_id = request.args.get("category_id", type=int)
    if category_id is not None:
        query = query.filter(Task.category_id == category_id)

    assignee_id = request.args.get("assignee_id", type=int)
    if assignee_id is not None:
        query = query.filter(Task.assignee_id == assignee_id)

    # --- Search (title + description) ---
    search = request.args.get("search", "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Task.title.ilike(like),
                                 Task.description.ilike(like)))

    # --- Due date range ---
    due_before, err = _parse_due_date(request.args.get("due_before"))
    if err:
        return jsonify({"error": "due_before must be a valid ISO-8601 datetime"}), 400
    if due_before:
        query = query.filter(Task.due_date != None,  # noqa: E711
                             Task.due_date <= due_before)

    due_after, err = _parse_due_date(request.args.get("due_after"))
    if err:
        return jsonify({"error": "due_after must be a valid ISO-8601 datetime"}), 400
    if due_after:
        query = query.filter(Task.due_date != None,  # noqa: E711
                             Task.due_date >= due_after)

    # --- Sorting ---
    sort_by = request.args.get("sort_by", "created_at")
    sort_columns = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "title": Task.title,
        "status": Task.status,
    }
    if sort_by not in sort_columns:
        return jsonify(
            {"error": f"sort_by must be one of {list(sort_columns)}"}), 400
    column = sort_columns[sort_by]
    order = request.args.get("order", "desc")
    if order not in ("asc", "desc"):
        return jsonify({"error": "order must be 'asc' or 'desc'"}), 400
    query = query.order_by(column.asc() if order == "asc" else column.desc(),
                           Task.id.asc())

    # --- Pagination ---
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    if page < 1:
        return jsonify({"error": "page must be >= 1"}), 400
    if per_page < 1 or per_page > MAX_PER_PAGE:
        return jsonify(
            {"error": f"per_page must be between 1 and {MAX_PER_PAGE}"}), 400

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


@tasks_bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id: int):
    user_id = _current_user_id()
    task = _visible_tasks_query(user_id).filter(Task.id == task_id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.put("/<int:task_id>")
@tasks_bp.patch("/<int:task_id>")
@jwt_required()
def update_task(task_id: int):
    user_id = _current_user_id()
    task = _visible_tasks_query(user_id).filter(Task.id == task_id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        if len(title) > 200:
            return jsonify({"error": "title must be at most 200 characters"}), 400
        task.title = title

    if "description" in data:
        task.description = (data.get("description") or "").strip()

    if "status" in data:
        if data["status"] not in VALID_STATUSES:
            return jsonify(
                {"error": f"status must be one of {list(VALID_STATUSES)}"}), 400
        task.status = data["status"]

    if "priority" in data:
        if data["priority"] not in VALID_PRIORITIES:
            return jsonify(
                {"error": f"priority must be one of {list(VALID_PRIORITIES)}"}), 400
        task.priority = data["priority"]

    if "due_date" in data:
        due_date, err = _parse_due_date(data.get("due_date"))
        if err:
            return jsonify({"error": err}), 400
        task.due_date = due_date

    if "category_id" in data:
        category_id, err = _validate_category(data.get("category_id"), user_id)
        if err:
            return jsonify({"error": err}), 404
        task.category_id = category_id

    if "assignee_id" in data:
        assignee_id, err = _validate_assignee(data.get("assignee_id"))
        if err:
            return jsonify({"error": err}), 404
        task.assignee_id = assignee_id

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id: int):
    user_id = _current_user_id()
    task = Task.query.filter(Task.id == task_id,
                             Task.creator_id == user_id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"}), 200


@tasks_bp.post("/<int:task_id>/assign")
@jwt_required()
def assign_task(task_id: int):
    user_id = _current_user_id()
    task = _visible_tasks_query(user_id).filter(Task.id == task_id).first()
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    if "assignee_id" not in data:
        return jsonify({"error": "assignee_id is required"}), 400

    assignee_id, err = _validate_assignee(data.get("assignee_id"))
    if err:
        return jsonify({"error": err}), 404

    task.assignee_id = assignee_id
    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200
