from datetime import date, datetime

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import case, or_, select

from .extensions import db
from .models import Category, Task, User
from .utils import login_required

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

SORTABLE_FIELDS = {"title", "status", "priority", "due_date", "created_at", "updated_at"}
SORT_DIRECTIONS = {"asc", "desc"}

PRIORITY_ORDER = case(
    (Task.priority == "urgent", 0),
    (Task.priority == "high", 1),
    (Task.priority == "medium", 2),
    (Task.priority == "low", 3),
    else_=4,
)


def _parse_due_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError("due_date must be a date in YYYY-MM-DD format.")


def _validate_task_fields(data, partial=False):
    fields = {}

    if "title" in data or not partial:
        title = (data.get("title") or "").strip() if "title" in data else None
        if not title:
            raise ValueError("Title is required.")
        if len(title) > 200:
            raise ValueError("Title must be 200 characters or fewer.")
        fields["title"] = title

    if "description" in data:
        fields["description"] = (data.get("description") or None)

    if "status" in data:
        status = data.get("status")
        if status not in Task.STATUSES:
            raise ValueError(
                f"Invalid status. Allowed: {', '.join(Task.STATUSES)}."
            )
        fields["status"] = status

    if "priority" in data:
        priority = data.get("priority")
        if priority not in Task.PRIORITIES:
            raise ValueError(
                f"Invalid priority. Allowed: {', '.join(Task.PRIORITIES)}."
            )
        fields["priority"] = priority

    if "category_id" in data:
        category_id = data.get("category_id")
        if category_id is not None:
            if db.session.get(Category, category_id) is None:
                raise ValueError("Category does not exist.")
        fields["category_id"] = category_id

    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is not None:
            if db.session.get(User, assignee_id) is None:
                raise ValueError("Assignee does not exist.")
        fields["assignee_id"] = assignee_id

    if "due_date" in data:
        fields["due_date"] = _parse_due_date(data.get("due_date"))

    return fields


def _int_arg(name, default):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return None


@bp.get("")
@login_required
def list_tasks():
    stmt = select(Task)

    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Task.title.ilike(like), Task.description.ilike(like)))

    status = (request.args.get("status") or "").strip()
    if status:
        if status not in Task.STATUSES:
            return jsonify({"error": f"Invalid status filter. Allowed: {', '.join(Task.STATUSES)}."}), 400
        stmt = stmt.where(Task.status == status)

    priority = (request.args.get("priority") or "").strip()
    if priority:
        if priority not in Task.PRIORITIES:
            return jsonify({"error": f"Invalid priority filter. Allowed: {', '.join(Task.PRIORITIES)}."}), 400
        stmt = stmt.where(Task.priority == priority)

    category = (request.args.get("category") or "").strip()
    if category:
        stmt = stmt.where(Task.category.has(Category.name == category))

    category_id = _int_arg("category_id", None)
    if category_id is not None:
        stmt = stmt.where(Task.category_id == category_id)

    assignee = (request.args.get("assignee") or "").strip()
    if assignee:
        stmt = stmt.where(Task.assignee.has(User.username == assignee))

    assignee_id = _int_arg("assignee_id", None)
    if assignee_id is not None:
        stmt = stmt.where(Task.assignee_id == assignee_id)

    due_before = (request.args.get("due_before") or "").strip()
    if due_before:
        try:
            stmt = stmt.where(Task.due_date <= datetime.strptime(due_before, "%Y-%m-%d").date())
        except ValueError:
            return jsonify({"error": "due_before must be YYYY-MM-DD."}), 400

    due_after = (request.args.get("due_after") or "").strip()
    if due_after:
        try:
            stmt = stmt.where(Task.due_date >= datetime.strptime(due_after, "%Y-%m-%d").date())
        except ValueError:
            return jsonify({"error": "due_after must be YYYY-MM-DD."}), 400

    sort_by = (request.args.get("sort_by") or "created_at").strip()
    sort_order = (request.args.get("order") or "desc").strip().lower()

    if sort_by not in SORTABLE_FIELDS:
        return jsonify({"error": f"Invalid sort_by. Allowed: {', '.join(sorted(SORTABLE_FIELDS))}."}), 400
    if sort_order not in SORT_DIRECTIONS:
        return jsonify({"error": "Invalid order. Allowed: asc, desc."}), 400

    column = getattr(Task, sort_by)
    if sort_by == "priority":
        column = PRIORITY_ORDER
    if sort_order == "asc":
        stmt = stmt.order_by(column.asc(), Task.id.asc())
    else:
        stmt = stmt.order_by(column.desc(), Task.id.desc())

    page = _int_arg("page", 1)
    per_page = _int_arg("per_page", current_app.config["DEFAULT_PAGE_SIZE"])
    if page is None or page < 1:
        return jsonify({"error": "page must be a positive integer."}), 400
    if per_page is None or per_page < 1:
        return jsonify({"error": "per_page must be a positive integer."}), 400
    if per_page > current_app.config["MAX_PAGE_SIZE"]:
        return jsonify({"error": f"per_page cannot exceed {current_app.config['MAX_PAGE_SIZE']}."}), 400

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "tasks": [t.to_dict() for t in pagination.items],
            "meta": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }
    ), 200


@bp.post("")
@login_required
def create_task():
    data = request.get_json(silent=True) or {}
    try:
        fields = _validate_task_fields(data, partial=False)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    task = Task(
        title=fields["title"],
        description=fields.get("description"),
        status=fields.get("status", "todo"),
        priority=fields.get("priority", "medium"),
        category_id=fields.get("category_id"),
        assignee_id=fields.get("assignee_id"),
        due_date=fields.get("due_date"),
        creator_id=g.current_user.id,
    )
    if task.status == "done":
        task.completed_at = datetime.utcnow()

    db.session.add(task)
    db.session.commit()
    return jsonify({"task": task.to_dict()}), 201


@bp.get("/<int:task_id>")
@login_required
def get_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404
    return jsonify({"task": task.to_dict()}), 200


@bp.put("/<int:task_id>")
@login_required
def update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    data = request.get_json(silent=True) or {}
    try:
        fields = _validate_task_fields(data, partial=False)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    task.title = fields["title"]
    task.description = fields.get("description")
    task.status = fields.get("status", "todo")
    task.priority = fields.get("priority", "medium")
    task.category_id = fields.get("category_id")
    task.assignee_id = fields.get("assignee_id")
    task.due_date = fields.get("due_date")

    if task.status == "done":
        if task.completed_at is None:
            task.completed_at = datetime.utcnow()
    else:
        task.completed_at = None

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@bp.patch("/<int:task_id>")
@login_required
def partial_update_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify({"error": "No fields provided."}), 400

    try:
        fields = _validate_task_fields(data, partial=True)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    for key, value in fields.items():
        setattr(task, key, value)

    if "status" in fields:
        if task.status == "done":
            if task.completed_at is None:
                task.completed_at = datetime.utcnow()
        else:
            task.completed_at = None

    db.session.commit()
    return jsonify({"task": task.to_dict()}), 200


@bp.delete("/<int:task_id>")
@login_required
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if task is None:
        return jsonify({"error": "Task not found."}), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted."}), 200
