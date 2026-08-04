from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models.task import (
    create_task,
    get_task_by_id,
    update_task,
    delete_task,
    query_tasks,
    task_to_dict,
)

tasks_bp = Blueprint("tasks", __name__)

VALID_STATUSES = {"todo", "in_progress", "done", "archived"}
VALID_PRIORITIES = {"low", "medium", "high", "urgent"}


@tasks_bp.route("", methods=["POST"])
@jwt_required()
def create():
    current_user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title is required."}), 400

    status = data.get("status", "todo")
    if status not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"}), 400

    priority = data.get("priority", "medium")
    if priority not in VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(VALID_PRIORITIES)}"}), 400

    task_id = create_task(
        title=title,
        created_by=current_user_id,
        description=data.get("description", ""),
        status=status,
        priority=priority,
        category_id=data.get("category_id"),
        assigned_to=data.get("assigned_to"),
        due_date=data.get("due_date"),
    )

    task = get_task_by_id(task_id)
    return jsonify({"task": task_to_dict(task)}), 201


@tasks_bp.route("", methods=["GET"])
@jwt_required()
def list_tasks():
    filters = {}
    for key in ["status", "priority", "category_id", "assigned_to",
                "created_by", "due_before", "due_after"]:
        val = request.args.get(key)
        if val is not None:
            filters[key] = val

    if request.args.get("overdue") == "true":
        filters["overdue"] = True

    search = request.args.get("q", "").strip() or None
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
    sort_by = request.args.get("sort_by", "created_at")
    sort_order = request.args.get("sort_order", "desc")

    current_user_id = int(get_jwt_identity())
    filters["created_by"] = current_user_id

    result = query_tasks(
        filters=filters,
        search=search,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    return jsonify(result), 200


@tasks_bp.route("/<int:task_id>", methods=["GET"])
@jwt_required()
def get(task_id):
    current_user_id = int(get_jwt_identity())
    task = get_task_by_id(task_id)

    if not task:
        return jsonify({"error": "Task not found."}), 404

    if task["created_by"] != current_user_id and task["assigned_to"] != current_user_id:
        return jsonify({"error": "Access denied."}), 403

    return jsonify({"task": task_to_dict(task)}), 200


@tasks_bp.route("/<int:task_id>", methods=["PUT"])
@jwt_required()
def update(task_id):
    current_user_id = int(get_jwt_identity())
    task = get_task_by_id(task_id)

    if not task:
        return jsonify({"error": "Task not found."}), 404

    if task["created_by"] != current_user_id:
        return jsonify({"error": "Only the task creator can update it."}), 403

    data = request.get_json(silent=True) or {}

    if "status" in data and data["status"] not in VALID_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"}), 400

    if "priority" in data and data["priority"] not in VALID_PRIORITIES:
        return jsonify({"error": f"Invalid priority. Must be one of: {', '.join(VALID_PRIORITIES)}"}), 400

    update_fields = {}
    for key in ["title", "description", "status", "priority",
                "category_id", "assigned_to", "due_date"]:
        if key in data:
            val = data[key]
            if key == "title" and val is not None:
                val = val.strip()
                if not val:
                    return jsonify({"error": "Title cannot be empty."}), 400
            update_fields[key] = val

    if not update_fields:
        return jsonify({"error": "No valid fields to update."}), 400

    update_task(task_id, **update_fields)
    task = get_task_by_id(task_id)
    return jsonify({"task": task_to_dict(task)}), 200


@tasks_bp.route("/<int:task_id>", methods=["DELETE"])
@jwt_required()
def delete(task_id):
    current_user_id = int(get_jwt_identity())
    task = get_task_by_id(task_id)

    if not task:
        return jsonify({"error": "Task not found."}), 404

    if task["created_by"] != current_user_id:
        return jsonify({"error": "Only the task creator can delete it."}), 403

    delete_task(task_id)
    return jsonify({"message": "Task deleted."}), 200
