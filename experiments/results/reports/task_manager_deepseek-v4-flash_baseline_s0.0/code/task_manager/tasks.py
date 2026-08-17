from datetime import date, datetime
from urllib.parse import urlencode

from flask import Blueprint, g, jsonify, request
from sqlalchemy import case, or_

from .extensions import db
from .models import Category, Task, User
from .utils import token_required

tasks_bp = Blueprint("tasks", __name__)

VALID_STATUSES = Task.VALID_STATUSES
VALID_PRIORITIES = Task.VALID_PRIORITIES

PRIORITY_ORDER = {"low": 0, "medium": 1, "high": 2}

ALLOWED_SORTS = {"created_at", "due_date", "title", "priority", "status", "id"}
ALLOWED_ORDERS = {"asc", "desc"}


def _error(message, status=400):
    return jsonify(error=message), status


def parse_iso_date(value):
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        raise ValueError(f"Invalid date format {value!r}; expected YYYY-MM-DD")


def _validate_status(status):
    if status not in VALID_STATUSES:
        return _error(f"status must be one of {sorted(VALID_STATUSES)}")
    return None


def _validate_priority(priority):
    if priority not in VALID_PRIORITIES:
        return _error(f"priority must be one of {sorted(VALID_PRIORITIES)}")
    return None


def resolve_category(category_id=None, category_name=None):
    if category_id is not None:
        if not isinstance(category_id, int) or category_id <= 0:
            return None, _error("category_id must be a positive integer")
        return db.session.get(Category, category_id), None
    if category_name is not None:
        name = str(category_name).strip()
        if not name:
            return None, _error("category name must not be empty")
        return Category.query.filter(db.func.lower(Category.name) == name.lower()).first(), None
    return None, None


def _resolve_user(user_id):
    if not isinstance(user_id, int) or user_id <= 0:
        return None, _error("user id must be a positive integer")
    return db.session.get(User, user_id), None


def _can_modify(task):
    user = g.current_user
    return user.role == "admin" or task.created_by_id == user.id


@tasks_bp.post("")
@token_required
def create_task():
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return _error("title is required")
    if len(title) > 200:
        return _error("title must be 200 characters or fewer")

    status = data.get("status", "todo")
    err = _validate_status(status)
    if err:
        return err

    priority = data.get("priority", "medium")
    err = _validate_priority(priority)
    if err:
        return err

    description = data.get("description")
    if description is not None and len(description) > 10000:
        return _error("description must be 10000 characters or fewer")

    try:
        due_date = parse_iso_date(data.get("due_date"))
    except ValueError as exc:
        return _error(str(exc))

    category, err = resolve_category(data.get("category_id"), data.get("category"))
    if err:
        return err
    if data.get("category_id") is not None and category is None:
        return _error("category not found", 404)

    assignee = None
    if data.get("assignee_id") is not None:
        assignee, err = _resolve_user(data.get("assignee_id"))
        if err:
            return err
        if assignee is None:
            return _error("assignee not found", 404)

    task = Task(
        title=title,
        description=description,
        status=status,
        priority=priority,
        due_date=due_date,
        category=category,
        assignee=assignee,
        created_by=g.current_user,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@tasks_bp.get("")
@token_required
def list_tasks():
    query = Task.query

    status = request.args.get("status")
    if status:
        err = _validate_status(status)
        if err:
            return err
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        err = _validate_priority(priority)
        if err:
            return err
        query = query.filter(Task.priority == priority)

    category = request.args.get("category")
    if category:
        if category.isdigit():
            query = query.filter(Task.category_id == int(category))
        else:
            query = query.join(Category).filter(Category.name.ilike(category))

    assignee_id = request.args.get("assignee_id")
    if assignee_id is not None:
        if not assignee_id.isdigit():
            return _error("assignee_id must be an integer")
        query = query.filter(Task.assignee_id == int(assignee_id))

    created_by = request.args.get("created_by")
    if created_by is not None:
        if not created_by.isdigit():
            return _error("created_by must be an integer")
        query = query.filter(Task.created_by_id == int(created_by))

    search = request.args.get("search")
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(Task.title.ilike(pattern), Task.description.ilike(pattern))
        )

    try:
        due_before = parse_iso_date(request.args.get("due_before"))
        due_after = parse_iso_date(request.args.get("due_after"))
    except ValueError as exc:
        return _error(str(exc))
    if due_before:
        query = query.filter(Task.due_date <= due_before)
    if due_after:
        query = query.filter(Task.due_date >= due_after)

    overdue = request.args.get("overdue")
    if overdue in ("true", "1", "yes"):
        query = query.filter(Task.due_date < date.today(), Task.status != "done")

    sort = request.args.get("sort", "created_at")
    if sort not in ALLOWED_SORTS:
        return _error(f"sort must be one of {sorted(ALLOWED_SORTS)}")
    order = request.args.get("order", "desc")
    if order not in ALLOWED_ORDERS:
        return _error(f"order must be one of {sorted(ALLOWED_ORDERS)}")

    direction = "desc" if order == "desc" else "asc"
    if sort == "priority":
        priority_expr = case(
            [(Task.priority == p, PRIORITY_ORDER[p]) for p in sorted(PRIORITY_ORDER)],
            else_=1,
        )
        if direction == "desc":
            query = query.order_by(priority_expr.desc(), Task.id.desc())
        else:
            query = query.order_by(priority_expr.asc(), Task.id.asc())
    else:
        column = getattr(Task, sort)
        if direction == "desc":
            query = query.order_by(column.desc(), Task.id.desc())
        else:
            query = query.order_by(column.asc(), Task.id.asc())

    page_arg = request.args.get("page", "1")
    per_page_arg = request.args.get("per_page", str(request.app.config["DEFAULT_PER_PAGE"]))
    try:
        page = int(page_arg)
        per_page = int(per_page_arg)
    except ValueError:
        return _error("page and per_page must be integers")
    if page < 1:
        page = 1
    per_page = max(1, min(per_page, request.app.config["MAX_PER_PAGE"]))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    base_pagination = {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    }

    def _page_link(number):
        if number is None:
            return None
        args = request.args.to_dict()
        args["page"] = str(number)
        return f"{request.path}?{urlencode(args)}"

    pagination_payload = dict(base_pagination)
    pagination_payload["prev"] = _page_link(pagination.prev_num)
    pagination_payload["next"] = _page_link(pagination.next_num)

    return jsonify(
        items=[task.to_dict() for task in pagination.items],
        pagination=pagination_payload,
    ), 200


def _get_task_or_404(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return None, jsonify(error="Task not found"), 404
    return task, None, None


def _apply_updates(task, data):
    title = data.get("title")
    if title is not None:
        title = str(title).strip()
        if not title:
            return _error("title must not be empty")
        if len(title) > 200:
            return _error("title must be 200 characters or fewer")
        task.title = title

    description = data.get("description")
    if description is not None:
        if len(description) > 10000:
            return _error("description must be 10000 characters or fewer")
        task.description = description

    status = data.get("status")
    if status is not None:
        err = _validate_status(status)
        if err:
            return err
        task.status = status

    priority = data.get("priority")
    if priority is not None:
        err = _validate_priority(priority)
        if err:
            return err
        task.priority = priority

    if "due_date" in data:
        try:
            task.due_date = parse_iso_date(data.get("due_date"))
        except ValueError as exc:
            return _error(str(exc))

    if "category_id" in data or "category" in data:
        category, err = resolve_category(data.get("category_id"), data.get("category"))
        if err:
            return err
        if data.get("category_id") is not None and category is None:
            return _error("category not found", 404)
        task.category = category

    if "assignee_id" in data:
        if data["assignee_id"] is None:
            task.assignee_id = None
        else:
            assignee, err = _resolve_user(data["assignee_id"])
            if err:
                return err
            if assignee is None:
                return _error("assignee not found", 404)
            task.assignee = assignee

    return None


@tasks_bp.get("/<int:task_id>")
@token_required
def get_task(task_id):
    task, error_response, status = _get_task_or_404(task_id)
    if task is None:
        return error_response, status
    return jsonify(task.to_dict()), 200


@tasks_bp.put("/<int:task_id>")
@token_required
def update_task(task_id):
    task, error_response, status = _get_task_or_404(task_id)
    if task is None:
        return error_response, status
    if not _can_modify(task):
        return jsonify(error="You do not have permission to modify this task"), 403

    data = request.get_json(silent=True) or {}
    err = _apply_updates(task, data)
    if err:
        return err
    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.patch("/<int:task_id>")
@token_required
def patch_task(task_id):
    return update_task(task_id)


@tasks_bp.delete("/<int:task_id>")
@token_required
def delete_task(task_id):
    task, error_response, status = _get_task_or_404(task_id)
    if task is None:
        return error_response, status
    if not _can_modify(task):
        return jsonify(error="You do not have permission to modify this task"), 403

    db.session.delete(task)
    db.session.commit()
    return "", 204


@tasks_bp.post("/<int:task_id>/assign")
@token_required
def assign_task(task_id):
    task, error_response, status = _get_task_or_404(task_id)
    if task is None:
        return error_response, status

    data = request.get_json(silent=True) or {}
    assignee_id = data.get("assignee_id")
    if assignee_id is None:
        return _error("assignee_id is required")
    if not isinstance(assignee_id, int):
        try:
            assignee_id = int(assignee_id)
        except (TypeError, ValueError):
            return _error("assignee_id must be an integer")

    assignee = db.session.get(User, assignee_id)
    if assignee is None:
        return _error("assignee not found", 404)

    task.assignee = assignee
    db.session.commit()
    return jsonify(task.to_dict()), 200


@tasks_bp.delete("/<int:task_id>/assignee")
@token_required
def unassign_task(task_id):
    task, error_response, status = _get_task_or_404(task_id)
    if task is None:
        return error_response, status

    task.assignee_id = None
    db.session.commit()
    return jsonify(task.to_dict()), 200
