from datetime import datetime

from .errors import ValidationError

VALID_STATUSES = ("pending", "in_progress", "completed")
VALID_PRIORITIES = ("low", "medium", "high")


def _require_json_object(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")


def _validate_due_date(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("due_date must be an ISO-8601 date string")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            "due_date must be a valid ISO-8601 date string, e.g. 2026-01-31"
        )
    return value


def validate_project_payload(payload, partial=False):
    _require_json_object(payload)
    data = {}

    if "name" in payload or not partial:
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("name is required and must be a non-empty string")
        data["name"] = name.strip()

    if "description" in payload:
        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            raise ValidationError("description must be a string")
        data["description"] = description or ""

    unknown = set(payload.keys()) - {"name", "description"}
    if unknown:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown))}")

    return data


def validate_task_payload(payload, partial=False):
    _require_json_object(payload)
    data = {}

    if "title" in payload or not partial:
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValidationError("title is required and must be a non-empty string")
        data["title"] = title.strip()

    if "description" in payload:
        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            raise ValidationError("description must be a string")
        data["description"] = description or ""

    if "status" in payload:
        status = payload.get("status")
        if status not in VALID_STATUSES:
            raise ValidationError(
                f"status must be one of {', '.join(VALID_STATUSES)}"
            )
        data["status"] = status

    if "priority" in payload:
        priority = payload.get("priority")
        if priority not in VALID_PRIORITIES:
            raise ValidationError(
                f"priority must be one of {', '.join(VALID_PRIORITIES)}"
            )
        data["priority"] = priority

    if "due_date" in payload:
        data["due_date"] = _validate_due_date(payload.get("due_date"))

    if "project_id" in payload:
        project_id = payload.get("project_id")
        if project_id is not None and not isinstance(project_id, int):
            raise ValidationError("project_id must be an integer or null")
        data["project_id"] = project_id

    unknown = set(payload.keys()) - {
        "title", "description", "status", "priority", "due_date", "project_id",
    }
    if unknown:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown))}")

    return data


def validate_status_payload(payload):
    _require_json_object(payload)
    status = payload.get("status")
    if status not in VALID_STATUSES:
        raise ValidationError(f"status must be one of {', '.join(VALID_STATUSES)}")
    return status
