import re

from flask import current_app, request

from .errors import APIError


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_json():
    data = request.get_json(silent=True)
    if data is None:
        raise APIError("Request body must be valid JSON", 400, "invalid_json")
    return data


def require_string(data, field, required=True, max_length=None, min_length=None):
    if field not in data or data[field] is None:
        if required:
            raise APIError(f"Field '{field}' is required", 400, "missing_field")
        return None
    value = data[field]
    if not isinstance(value, str):
        raise APIError(f"Field '{field}' must be a string", 400, "invalid_type")
    value = value.strip()
    if min_length is not None and len(value) < min_length:
        raise APIError(
            f"Field '{field}' must be at least {min_length} characters",
            400,
            "invalid_length",
        )
    if max_length is not None and len(value) > max_length:
        raise APIError(
            f"Field '{field}' must be at most {max_length} characters",
            400,
            "invalid_length",
        )
    return value


def require_email(data, field="email", required=True):
    value = require_string(data, field, required=required, max_length=120)
    if value is None or value == "":
        return None
    if not EMAIL_RE.match(value):
        raise APIError(f"Field '{field}' must be a valid email address", 400, "invalid_email")
    return value.lower()


def optional_number(data, field):
    if field not in data or data[field] is None:
        return None
    value = data[field]
    if isinstance(value, bool):
        raise APIError(f"Field '{field}' must be a number", 400, "invalid_type")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            raise APIError(f"Field '{field}' must be a number", 400, "invalid_type")
    raise APIError(f"Field '{field}' must be a number", 400, "invalid_type")


def _positive_int_arg(name, default):
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise APIError(f"Query parameter '{name}' must be an integer", 400, "invalid_query_param")
    if value < 1:
        raise APIError(f"Query parameter '{name}' must be >= 1", 400, "invalid_query_param")
    return value


def get_pagination():
    page = _positive_int_arg("page", 1)
    per_page = _positive_int_arg("per_page", current_app.config["DEFAULT_PAGE_SIZE"])
    per_page = min(per_page, current_app.config["MAX_PAGE_SIZE"])
    return page, per_page
