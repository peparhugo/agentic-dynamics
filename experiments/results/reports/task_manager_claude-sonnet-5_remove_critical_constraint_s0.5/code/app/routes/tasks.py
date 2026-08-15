from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from .. import repository
from ..errors import NotFoundError, ValidationError
from ..schemas import (
    VALID_PRIORITIES,
    VALID_STATUSES,
    validate_status_payload,
    validate_task_payload,
)

tasks_bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


def _get_task_or_404(task_id):
    task = repository.get_task(task_id)
    if task is None:
        raise NotFoundError(f"Task {task_id} not found")
    return task


def _ensure_project_exists(project_id):
    if project_id is not None and repository.get_project(project_id) is None:
        raise ValidationError(f"project_id {project_id} does not reference an existing project")


def _parse_pagination():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        raise ValidationError("page and per_page must be integers")
    if page < 1:
        raise ValidationError("page must be >= 1")
    if per_page < 1 or per_page > 100:
        raise ValidationError("per_page must be between 1 and 100")
    return page, per_page


@tasks_bp.get("")
def list_tasks():
    status = request.args.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise ValidationError(f"status must be one of {', '.join(VALID_STATUSES)}")

    priority = request.args.get("priority")
    if priority is not None and priority not in VALID_PRIORITIES:
        raise ValidationError(f"priority must be one of {', '.join(VALID_PRIORITIES)}")

    project_id = request.args.get("project_id")
    if project_id is not None:
        try:
            project_id = int(project_id)
        except ValueError:
            raise ValidationError("project_id must be an integer")

    search = request.args.get("search")
    page, per_page = _parse_pagination()

    result = repository.list_tasks(
        status=status,
        priority=priority,
        project_id=project_id,
        search=search,
        page=page,
        per_page=per_page,
    )
    return jsonify(result)


@tasks_bp.post("")
def create_task():
    payload = request.get_json(silent=True) or {}
    data = validate_task_payload(payload)
    _ensure_project_exists(data.get("project_id"))
    task = repository.create_task(data)
    return jsonify(task), 201


@tasks_bp.get("/<int:task_id>")
def get_task(task_id):
    return jsonify(_get_task_or_404(task_id))


@tasks_bp.put("/<int:task_id>")
def update_task(task_id):
    _get_task_or_404(task_id)
    payload = request.get_json(silent=True) or {}
    data = validate_task_payload(payload, partial=True)
    if "project_id" in data:
        _ensure_project_exists(data["project_id"])
    task = repository.update_task(task_id, data)
    return jsonify(task)


@tasks_bp.patch("/<int:task_id>/status")
def patch_task_status(task_id):
    _get_task_or_404(task_id)
    payload = request.get_json(silent=True) or {}
    status = validate_status_payload(payload)
    fields = {"status": status}
    if status == "completed":
        fields["completed_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )
    else:
        fields["completed_at"] = None
    task = repository.update_task(task_id, fields)
    return jsonify(task)


@tasks_bp.delete("/<int:task_id>")
def delete_task(task_id):
    _get_task_or_404(task_id)
    repository.delete_task(task_id)
    return "", 204
