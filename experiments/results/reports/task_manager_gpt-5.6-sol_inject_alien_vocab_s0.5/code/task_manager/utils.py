from datetime import datetime

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity

from task_manager.models import User


def json_error(message, status=400):
    return jsonify(error=message), status


def json_body():
    return request.get_json(silent=True)


def current_user():
    return User.query.get(int(get_jwt_identity()))


def parse_due_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("due_date must be an ISO 8601 string or null")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("due_date must be a valid ISO 8601 datetime") from exc


def positive_int_arg(name, default, maximum=None):
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must not exceed {maximum}")
    return value
