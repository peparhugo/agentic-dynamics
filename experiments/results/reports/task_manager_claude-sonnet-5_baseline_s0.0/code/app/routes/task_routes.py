import datetime

from flask import Blueprint, g, jsonify, request

from app import models
from app.auth import token_required
from app.models import VALID_PRIORITIES, VALID_STATUSES
from app.utils import get_pagination_params, paginated_response

task_bp = Blueprint("tasks", __name__)


def _validate_due_date(value):
    try:
        datetime.date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def _validate_task_payload(data, partial=False):
    """Returns (fields_dict, error_message)."""
    fields = {}

    if "title" in data or not partial:
        title = (data.get("title") or "").strip()
        if not title:
            return None, "title is required"
        fields["title"] = title

    if "description" in data:
        fields["description"] = data.get("description")

    if "status" in data:
        status = data.get("status")
        if status not in VALID_STATUSES:
            return None, f"status must be one of {VALID_STATUSES}"
        fields["status"] = status
    elif not partial:
        fields["status"] = "pending"

    if "priority" in data:
        priority = data.get("priority")
        if priority not in VALID_PRIORITIES:
            return None, f"priority must be one of {VALID_PRIORITIES}"
        fields["priority"] = priority
    elif not partial:
        fields["priority"] = "medium"

    if "due_date" in data:
        due_date = data.get("due_date")
        if due_date is not None and not _validate_due_date(due_date):
            return None, "due_date must be an ISO date string (YYYY-MM-DD)"
        fields["due_date"] = due_date
    elif not partial:
        fields["due_date"] = None

    if "category_id" in data:
        category_id = data.get("category_id")
        if category_id is not None:
            category = models.get_category_by_id(category_id, g.current_user["id"])
            if category is None:
                return None, "category_id does not exist"
        fields["category_id"] = category_id
    elif not partial:
        fields["category_id"] = None

    if "assignee_id" in data:
        assignee_id = data.get("assignee_id")
        if assignee_id is not None and not models.user_exists(assignee_id):
            return None, "assignee_id does not reference an existing user"
        fields["assignee_id"] = assignee_id
    elif not partial:
        fields["assignee_id"] = None

    return fields, None


@task_bp.post("")
@token_required
def create_task():
    data = request.get_json(silent=True) or {}
    fields, error = _validate_task_payload(data, partial=False)
    if error:
        return jsonify({"error": error}), 400

    task = models.create_task(owner_id=g.current_user["id"], **fields)
    return jsonify({"task": task}), 201


@task_bp.get("")
@token_required
def list_tasks():
    page, per_page = get_pagination_params()

    status = request.args.get("status")
    if status and status not in VALID_STATUSES:
        return jsonify({"error": f"status must be one of {VALID_STATUSES}"}), 400

    priority = request.args.get("priority")
    if priority and priority not in VALID_PRIORITIES:
        return jsonify({"error": f"priority must be one of {VALID_PRIORITIES}"}), 400

    category_id = request.args.get("category_id", type=int)
    assignee_id = request.args.get("assignee_id", type=int)
    q = request.args.get("q")

    tasks, total = models.list_tasks(
        g.current_user["id"], page, per_page,
        status=status, category_id=category_id, priority=priority,
        assignee_id=assignee_id, q=q,
    )
    return jsonify(paginated_response(tasks, total, page, per_page, key="tasks")), 200


@task_bp.get("/<int:task_id>")
@token_required
def get_task(task_id):
    task = models.get_task_by_id(task_id)
    if task is None or not models.can_view_task(task, g.current_user["id"]):
        return jsonify({"error": "task not found"}), 404
    return jsonify({"task": task}), 200


@task_bp.put("/<int:task_id>")
@token_required
def update_task(task_id):
    task = models.get_task_by_id(task_id)
    if task is None or not models.can_view_task(task, g.current_user["id"]):
        return jsonify({"error": "task not found"}), 404

    data = request.get_json(silent=True) or {}

    if not models.can_edit_task(task, g.current_user["id"]):
        # Assignees who are not the owner may only update the status field.
        if set(data.keys()) - {"status"}:
            return jsonify({"error": "only the task owner can edit fields other than status"}), 403
        if "status" not in data or data["status"] not in VALID_STATUSES:
            return jsonify({"error": f"status must be one of {VALID_STATUSES}"}), 400
        updated = models.update_task(task_id, status=data["status"])
        return jsonify({"task": updated}), 200

    fields, error = _validate_task_payload(data, partial=True)
    if error:
        return jsonify({"error": error}), 400

    updated = models.update_task(task_id, **fields)
    return jsonify({"task": updated}), 200


@task_bp.delete("/<int:task_id>")
@token_required
def delete_task(task_id):
    task = models.get_task_by_id(task_id)
    if task is None or not models.can_view_task(task, g.current_user["id"]):
        return jsonify({"error": "task not found"}), 404
    if not models.can_edit_task(task, g.current_user["id"]):
        return jsonify({"error": "only the task owner can delete this task"}), 403

    models.delete_task(task_id)
    return "", 204


@task_bp.post("/<int:task_id>/assign")
@token_required
def assign_task(task_id):
    task = models.get_task_by_id(task_id)
    if task is None or not models.can_view_task(task, g.current_user["id"]):
        return jsonify({"error": "task not found"}), 404
    if not models.can_edit_task(task, g.current_user["id"]):
        return jsonify({"error": "only the task owner can assign this task"}), 403

    data = request.get_json(silent=True) or {}
    assignee_id = data.get("assignee_id")
    if assignee_id is not None and not models.user_exists(assignee_id):
        return jsonify({"error": "assignee_id does not reference an existing user"}), 400

    updated = models.assign_task(task_id, assignee_id)
    return jsonify({"task": updated}), 200
