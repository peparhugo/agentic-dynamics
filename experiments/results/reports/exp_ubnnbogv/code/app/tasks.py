from datetime import datetime

from flask import Blueprint, g, jsonify, request

from .auth import login_required
from .db import db
from .errors import ApiError
from .models import PRIORITIES, STATUSES, Category, Task, User
from .utils import int_param, normalize_tags, parse_bool, parse_date

bp = Blueprint("tasks", __name__, url_prefix="/api")

_SORT_COLUMNS = {
    "created_at": Task.created_at,
    "updated_at": Task.updated_at,
    "due_date": Task.due_date,
    "priority": Task.priority,
    "title": Task.title,
    "id": Task.id,
}


def _get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        raise ApiError("task not found", 404)
    return task


def _resolve_category(name):
    if name is None:
        return None
    category = Category.query.filter_by(name=name).first()
    if category is None:
        raise ApiError(f"unknown category: {name}", 400, {"category": "unknown category"})
    return category


def _resolve_assignee(data):
    if "assignee" in data:
        username = (data.get("assignee") or "").strip()
        if not username:
            return None
        user = User.query.filter_by(username=username).first()
        if user is None:
            raise ApiError(f"unknown assignee: {username}", 400, {"assignee": "unknown user"})
        return user
    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is None:
            return None
        user = db.session.get(User, assignee_id)
        if user is None:
            raise ApiError("unknown assignee", 400, {"assignee_id": "unknown user"})
        return user
    return None


def _validate_task(task):
    if task.title is not None:
        task.title = str(task.title).strip()
        if not task.title:
            raise ApiError("title is required", 400, {"title": "required"})
    if task.status is not None and task.status not in STATUSES:
        raise ApiError(f"status must be one of: {', '.join(STATUSES)}", 400, {"status": "invalid status"})
    if task.priority is not None and task.priority not in PRIORITIES:
        raise ApiError(f"priority must be one of: {', '.join(PRIORITIES)}", 400, {"priority": "invalid priority"})


def _apply_patch(task, data):
    for field in ("title", "description", "status", "priority", "archived"):
        if field in data:
            value = data[field]
            if field == "archived":
                value = parse_bool(value, "archived")
            setattr(task, field, value)
    if "tags" in data:
        task.tags = normalize_tags(data["tags"])
    if "due_date" in data:
        task.due_date = parse_date(data.get("due_date"), "due_date")
    if "category" in data:
        task.category = _resolve_category(data.get("category"))
    if "assignee" in data or "assignee_id" in data:
        task.assignee = _resolve_assignee(data)
    _validate_task(task)


def _task_payload(data):
    if not isinstance(data, dict):
        raise ApiError("invalid JSON body", 400)
    title = (data.get("title") or "").strip()
    if not title:
        raise ApiError("title is required", 400, {"title": "required"})
    task = Task(title=title, created_by_id=g.current_user.id)
    task.description = data.get("description")
    task.status = data.get("status", "todo")
    task.priority = data.get("priority", "medium")
    task.tags = normalize_tags(data.get("tags"))
    task.archived = parse_bool(data.get("archived", False), "archived")
    task.due_date = parse_date(data.get("due_date"), "due_date")
    task.category = _resolve_category(data.get("category"))
    task.assignee = _resolve_assignee(data)
    _validate_task(task)
    return task


@bp.get("/tasks")
@login_required
def list_tasks():
    page = int_param("page", 1, min_value=1)
    per_page = int_param("per_page", 20, min_value=1, max_value=100)

    query = Task.query

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Task.title.ilike(like), Task.description.ilike(like)))

    status = request.args.get("status")
    if status:
        if status not in STATUSES:
            raise ApiError(f"status must be one of: {', '.join(STATUSES)}", 400, {"status": "invalid status"})
        query = query.filter(Task.status == status)

    priority = request.args.get("priority")
    if priority:
        if priority not in PRIORITIES:
            raise ApiError(f"priority must be one of: {', '.join(PRIORITIES)}", 400, {"priority": "invalid priority"})
        query = query.filter(Task.priority == priority)

    category = request.args.get("category")
    if category:
        query = query.join(Category).filter(Category.name == category)

    assignee = request.args.get("assignee")
    if assignee:
        query = query.join(User, Task.assignee).filter(User.username == assignee)

    due_after = parse_date(request.args.get("due_after"), "due_after")
    if due_after:
        query = query.filter(Task.due_date >= due_after)
    due_before = parse_date(request.args.get("due_before"), "due_before")
    if due_before:
        query = query.filter(Task.due_date <= due_before)

    if request.args.get("archived") is None:
        query = query.filter(Task.archived.is_(False))
    else:
        query = query.filter(Task.archived.is_(parse_bool(request.args.get("archived"), "archived")))

    sort = request.args.get("sort", "created_at")
    if sort not in _SORT_COLUMNS:
        raise ApiError(f"sort must be one of: {', '.join(_SORT_COLUMNS)}", 400, {"sort": "invalid sort"})
    order = request.args.get("order", "desc")
    if order not in ("asc", "desc"):
        raise ApiError("order must be asc or desc", 400, {"order": "invalid order"})

    column = _SORT_COLUMNS[sort]
    query = query.order_by(column.desc() if order == "desc" else column.asc(), Task.id.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify(
        {
            "items": [task.to_dict() for task in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            },
        }
    )


@bp.get("/tasks/<int:task_id>")
@login_required
def get_task(task_id):
    return jsonify(_get_task(task_id).to_dict())


@bp.post("/tasks")
@login_required
def create_task():
    task = _task_payload(request.get_json(silent=True))
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@bp.put("/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    task = _get_task(task_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("invalid JSON body", 400)
    task.title = (data.get("title") or "").strip()
    if not task.title:
        raise ApiError("title is required", 400, {"title": "required"})
    task.description = data.get("description")
    task.status = data.get("status", "todo")
    task.priority = data.get("priority", "medium")
    task.tags = normalize_tags(data.get("tags"))
    task.archived = parse_bool(data.get("archived", False), "archived")
    task.due_date = parse_date(data.get("due_date"), "due_date")
    task.category = _resolve_category(data.get("category"))
    task.assignee = _resolve_assignee(data)
    _validate_task(task)
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict())


@bp.patch("/tasks/<int:task_id>")
@login_required
def patch_task(task_id):
    task = _get_task(task_id)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("invalid JSON body", 400)
    _apply_patch(task, data)
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict())


@bp.delete("/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    task = _get_task(task_id)
    db.session.delete(task)
    db.session.commit()
    return "", 204


@bp.post("/tasks/<int:task_id>/assign")
@login_required
def assign_task(task_id):
    task = _get_task(task_id)
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        raise ApiError("invalid JSON body", 400)
    if "assignee" not in data and "assignee_id" not in data:
        raise ApiError("assignee or assignee_id is required", 400)
    task.assignee = _resolve_assignee(data)
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(task.to_dict())
