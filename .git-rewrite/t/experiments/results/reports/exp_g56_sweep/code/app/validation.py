import re

from flask import request

from .errors import APIError


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def json_body(allowed_fields, required_fields=()):
    if not request.is_json:
        raise APIError(415, "unsupported_media_type", "Content-Type must be application/json")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError(400, "invalid_json", "Request body must be a JSON object")
    unknown = sorted(set(data) - set(allowed_fields))
    missing = sorted(set(required_fields) - set(data))
    details = {}
    if unknown:
        details["unknown_fields"] = unknown
    if missing:
        details["missing_fields"] = missing
    if details:
        raise APIError(400, "validation_error", "Request validation failed", details)
    return data


def validate_email(value):
    if not isinstance(value, str) or len(value) > 254 or not EMAIL_RE.fullmatch(value):
        raise APIError(400, "validation_error", "A valid email address is required")
    return value.strip().lower()


def validate_password(value):
    if not isinstance(value, str) or not 8 <= len(value) <= 128:
        raise APIError(400, "validation_error", "Password must be 8 to 128 characters")
    return value


def validate_item(data, partial=False):
    if partial and not data:
        raise APIError(400, "validation_error", "At least one field is required")
    if "name" in data:
        if not isinstance(data["name"], str) or not data["name"].strip() or len(data["name"].strip()) > 120:
            raise APIError(400, "validation_error", "Name must be 1 to 120 characters")
        data["name"] = data["name"].strip()
    if "description" in data:
        value = data["description"]
        if value is not None and (not isinstance(value, str) or len(value) > 2000):
            raise APIError(400, "validation_error", "Description must be null or at most 2000 characters")
    return data


def pagination_args():
    unknown = sorted(set(request.args) - {"page", "per_page"})
    if unknown:
        raise APIError(
            400, "validation_error", "Unknown query parameters", {"unknown_fields": unknown}
        )
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError as exc:
        raise APIError(400, "validation_error", "Pagination values must be integers") from exc
    if page < 1 or not 1 <= per_page <= 100:
        raise APIError(400, "validation_error", "Page must be positive and per_page must be 1 to 100")
    return page, per_page
