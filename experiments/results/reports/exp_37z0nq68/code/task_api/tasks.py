from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timezone
from models import db, Task, User

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def parse_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return False


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create_task():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    if len(title) > 200:
        return jsonify({"error": "title must be 200 characters or fewer"}), 400

    description = data.get("description", "")
    category = (data.get("category") or "general").strip().lower()
    priority = (data.get("priority") or "medium").strip().lower()
    status = (data.get("status") or "pending").strip().lower()

    if priority not in Task.VALID_PRIORITIES:
        return jsonify({"error": f"priority must be one of {sorted(Task.VALID_PRIORITIES)}"}), 400
    if status not in Task.VALID_STATUSES:
        return jsonify({"error": f"status must be one of {sorted(Task.VALID_STATUSES)}"}), 400

    due_date = None
    if data.get("due_date"):
        try:
            due_date = datetime.fromisoformat(data["due_date"])
        except (ValueError, TypeError):
            return jsonify({"error": "due_date must be ISO 8601 format"}), 400

    assignee_ids = data.get("assignee_ids", [])
    if not isinstance(assignee_ids, list):
        return jsonify({"error": "assignee_ids must be an array"}), 400

    user_id = int(get_jwt_identity())

    task = Task(
        title=title,
        description=description,
        category=category,
        priority=priority,
        status=status,
        due_date=due_date,
        created_by=user_id,
    )

    if assignee_ids:
        users = User.query.filter(User.id.in_(assignee_ids)).all()
        if len(users) != len(assignee_ids):
            return jsonify({"error": "one or more assignee_ids are invalid"}), 400
        task.assignees.extend(users)

    db.session.add(task)
    db.session.commit()

    return jsonify({"message": "task created", "task": task.to_dict()}), 201


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    status_filter = request.args.get("status")
    priority_filter = request.args.get("priority")
    category_filter = request.args.get("category")
    search = request.args.get("search")
    sort_by = request.args.get("sort_by", "created_at").strip()
    sort_order = request.args.get("sort_order", "desc").strip().lower()
    include_assigned = request.args.get("include_assigned", "true").strip()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    per_page = min(max(per_page, 1), 100)

    user_id = int(get_jwt_identity())
    query = Task.query

    if include_assigned == "false":
        query = query.filter_by(created_by=user_id)
    elif include_assigned == "only_assigned":
        query = query.filter(
            Task.created_by != user_id,
            Task.assignees.any(User.id == user_id),
        )
    else:
        query = query.filter(
            db.or_(
                Task.created_by == user_id,
                Task.assignees.any(User.id == user_id),
            )
        )

    if status_filter:
        query = query.filter(Task.status == status_filter.strip().lower())
    if priority_filter:
        query = query.filter(Task.priority == priority_filter.strip().lower())
    if category_filter:
        query = query.filter(Task.category == category_filter.strip().lower())
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(
            db.or_(Task.title.ilike(like), Task.description.ilike(like))
        )

    allowed_sort_cols = {"created_at", "updated_at", "due_date", "title", "priority", "status"}
    if sort_by not in allowed_sort_cols:
        sort_by = "created_at"

    col = getattr(Task, sort_by)
    if sort_order == "asc":
        query = query.order_by(col.asc(), Task.id.asc())
    else:
        query = query.order_by(col.desc(), Task.id.asc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "tasks": [t.to_dict() for t in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_prev": pagination.has_prev,
            "has_next": pagination.has_next,
        },
    }), 200


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get_task(task_id):
    user_id = int(get_jwt_identity())
    task = _get_task_for_user(task_id, user_id)
    if not task:
        return jsonify({"error": "task not found"}), 404
    return jsonify({"task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update_task(task_id):
    user_id = int(get_jwt_identity())
    task = _get_task_for_user(task_id, user_id)
    if not task:
        return jsonify({"error": "task not found"}), 404

    if task.created_by != user_id:
        return jsonify({"error": "only the task creator can update this task"}), 403

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            return jsonify({"error": "title must not be empty"}), 400
        if len(title) > 200:
            return jsonify({"error": "title must be 200 characters or fewer"}), 400
        task.title = title

    if "description" in data:
        task.description = data["description"] or ""

    if "status" in data:
        status = data["status"].strip().lower()
        if status not in Task.VALID_STATUSES:
            return jsonify({"error": f"status must be one of {sorted(Task.VALID_STATUSES)}"}), 400
        task.status = status

    if "priority" in data:
        priority = data["priority"].strip().lower()
        if priority not in Task.VALID_PRIORITIES:
            return jsonify({"error": f"priority must be one of {sorted(Task.VALID_PRIORITIES)}"}), 400
        task.priority = priority

    if "category" in data:
        category = data["category"].strip().lower()
        if not category:
            return jsonify({"error": "category must not be empty"}), 400
        task.category = category

    if "due_date" in data:
        if data["due_date"] is None:
            task.due_date = None
        else:
            try:
                task.due_date = datetime.fromisoformat(data["due_date"])
            except (ValueError, TypeError):
                return jsonify({"error": "due_date must be ISO 8601 format"}), 400

    if "assignee_ids" in data:
        assignee_ids = data["assignee_ids"]
        if not isinstance(assignee_ids, list):
            return jsonify({"error": "assignee_ids must be an array"}), 400
        if assignee_ids:
            users = User.query.filter(User.id.in_(assignee_ids)).all()
            if len(users) != len(assignee_ids):
                return jsonify({"error": "one or more assignee_ids are invalid"}), 400
            task.assignees = users
        else:
            task.assignees = []

    db.session.commit()
    return jsonify({"message": "task updated", "task": task.to_dict()}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete_task(task_id):
    user_id = int(get_jwt_identity())
    task = _get_task_for_user(task_id, user_id)
    if not task:
        return jsonify({"error": "task not found"}), 404

    if task.created_by != user_id:
        return jsonify({"error": "only the task creator can delete this task"}), 403

    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "task deleted"}), 200


def _get_task_for_user(task_id, user_id):
    return Task.query.filter(
        Task.id == task_id,
        db.or_(
            Task.created_by == user_id,
            Task.assignees.any(User.id == user_id),
        ),
    ).first()
