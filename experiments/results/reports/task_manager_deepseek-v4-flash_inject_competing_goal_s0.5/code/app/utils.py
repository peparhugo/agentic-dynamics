from datetime import datetime

from flask import request

from .errors import ApiError

_TRUE = {"1", "true", "yes", "on"}


def parse_date(value, field):
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        raise ApiError(f"{field} must be a date string in YYYY-MM-DD format", 400, {field: "invalid date"})
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ApiError(f"{field} must be a date string in YYYY-MM-DD format", 400, {field: "invalid date"})


def parse_bool(value, field="boolean"):
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ApiError(f"{field} must be a boolean", 400, {field: "invalid boolean"})


def int_param(name, default, min_value=None, max_value=None):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be an integer", 400, {name: "invalid integer"})
    if min_value is not None and value < min_value:
        raise ApiError(f"{name} must be >= {min_value}", 400, {name: "out of range"})
    if max_value is not None and value > max_value:
        raise ApiError(f"{name} must be <= {max_value}", 400, {name: "out of range"})
    return value


def normalize_tags(tags):
    if tags is None:
        return None
    if isinstance(tags, str):
        items = [part.strip() for part in tags.split(",") if part.strip()]
    elif isinstance(tags, (list, tuple, set)):
        items = [str(part).strip() for part in tags if str(part).strip()]
    else:
        raise ApiError("tags must be a list of strings or a comma-separated string", 400, {"tags": "invalid"})
    return ",".join(items) if items else None
