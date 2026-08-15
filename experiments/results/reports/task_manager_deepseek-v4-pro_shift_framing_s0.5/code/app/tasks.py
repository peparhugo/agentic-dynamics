from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from .extensions import db
from .models import Category, Task, User, VALID_PRIORITIES, VALID_STATUSES
from .utils import error_response, paginate_query

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


def _current_user():
    return db.session.get(User, int(get_jwt_identity()))


def _apply_filters(query):
    status = request.args.get("status")
    priority = request.args.get("priority")
    category_id = request.args.get("category_id")
    category = request.args.get("category")
    assignee_id = request.args.get("assignee_id")
    q = request.args.get("q")
    sort_by = request.args.get("sort_by", "created_at")
    order = request.args.get("order", "desc")

    if status:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status: {status}")
        query = query.filter(Task.status == status)
    if priority:
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"invalid priority: {priority}")
        query = query.filter(Task.priority == priority)
    if category_id:
        query = query.filter(Task.category_id == int(category_id))
    if category:
        query = query.join(Category).filter(Category.name == category)
    if assignee_id:
        query = query.filter(Task.assignee_id == int(assignee_id))
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    sort_columns = {
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.due_date,
        "priority": Task.priority,
        "title": Task.title,
    }
    column = sort_columns.get(sort_by, Task.created_at)
    query = query.order_by(column.desc() if order == "desc" else column.asc())
    return query


@tasks_bp.get("")
@jwt_required()
def list_tasks():
    try:
        query = _apply_filters(Task.query)
    except ValueError as exc:
        return error_response(str(exc), 400)
    page = request.args.get("page", 1)
    per_page = request.args.get("per_page", 10)
    return paginate_query(query, page, per_page), 200


@tasks_bp.post("")
@jwt_required()
def create_task():
    user = _current_user()
    data = request.get_json(silent=True) or {}

    title = (data.get("title") or "").strip()
    if not title:
        return error_response("title is required", 400)

    status = data.get("status", "todo")
    priority = data.get("priority", "medium")
    if status not in VALID_STATUSES:
        return error_response(f"invalid status: {status}", 400)
    if priority not in VALID_PRIORITIES:
        return error_response(f"invalid priority: {priority}", 400)

    try:
        due_date = Task.parse_due_date(data.get("due_date"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    category_id = data.get("category_id")
    if category_id is not None and not db.session.get(Category, int(category_id)):
        return error_response("category not found", 400)

    assignee_id = data.get("assignee_id")
    if assignee_id is not None and not db.session.get(User, int(assignee_id)):
        return error_response("assignee not found", 400)

    task = Task(
        title=title,
        description=data.get("description") or "",
        status=status,
        priority=priority,
        due_date=due_date,
        category_id=category_id,
        assignee_id=assignee_id,
        creator_id=user.id,
    )
    db.session.add(task)
    db.session.commit()
    return {"task": task.to_dict()}, 201


@tasks_bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return error_response("task not found", 404)
    return {"task": task.to_dict()}, 200


@tasks_bp.patch("/<int:task_id>")
@jwt_required()
def update_task(task_id):
    user = _current_user()
    task = db.session.get(Task, task_id)
    if not task:
        return error_response("task not found", 404)

    is_creator = task.creator_id == user.id
    is_assignee = task.assignee_id == user.id
    if not (is_creator or is_assignee):
        return error_response("not authorized to modify this task", 403)

    data = request.get_json(silent=True) or {}

    if "title" in data:
        title = (data.get("title") or "").strip()
        if not title:
            return error_response("title cannot be empty", 400)
        task.title = title
    if "description" in data:
        task.description = data.get("description") or ""
    if "status" in data:
        if data["status"] not in VALID_STATUSES:
            return error_response(f"invalid status: {data['status']}", 400)
        task.status = data["status"]
    if "priority" in data:
        if data["priority"] not in VALID_PRIORITIES:
            return error_response(f"invalid priority: {data['priority']}", 400)
        task.priority = data["priority"]
    if "due_date" in data:
        try:
            task.due_date = Task.parse_due_date(data.get("due_date"))
        except ValueError as exc:
            return error_response(str(exc), 400)
    if "category_id" in data:
        category_id = data["category_id"]
        if category_id is not None and not db.session.get(Category, int(category_id)):
            return error_response("category not found", 400)
        task.category_id = category_id
    if "assignee_id" in data:
        assignee_id = data["assignee_id"]
        if assignee_id is not None and not db.session.get(User, int(assignee_id)):
            return error_response("assignee not found", 400)
        task.assignee_id = assignee_id

    db.session.commit()
    return {"task": task.to_dict()}, 200


@tasks_bp.put("/<int:task_id>")
@jwt_required()
def replace_task(task_id):
    user = _current_user()
    task = db.session.get(Task, task_id)
    if not task:
        return error_response("task not found", 404)
    if task.creator_id != user.id:
        return error_response("not authorized to modify this task", 403)

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return error_response("title is required", 400)

    status = data.get("status", "todo")
    priority = data.get("priority", "medium")
    if status not in VALID_STATUSES:
        return error_response(f"invalid status: {status}", 400)
    if priority not in VALID_PRIORITIES:
        return error_response(f"invalid priority: {priority}", 400)

    try:
        due_date = Task.parse_due_date(data.get("due_date"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    category_id = data.get("category_id")
    if category_id is not None and not db.session.get(Category, int(category_id)):
        return error_response("category not found", 400)

    assignee_id = data.get("assignee_id")
    if assignee_id is not None and not db.session.get(User, int(assignee_id)):
        return error_response("assignee not found", 400)

    task.title = title
    task.description = data.get("description") or ""
    task.status = status
    task.priority = priority
    task.due_date = due_date
    task.category_id = category_id
    task.assignee_id = assignee_id
    db.session.commit()
    return {"task": task.to_dict()}, 200


@tasks_bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    user = _current_user()
    task = db.session.get(Task, task_id)
    if not task:
        return error_response("task not found", 404)
    if task.creator_id != user.id:
        return error_response("not authorized to delete this task", 403)
    db.session.delete(task)
    db.session.commit()
    return "", 204
