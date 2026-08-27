import re

from flask import current_app, request

from .errors import ValidationError

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,80}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_json():
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("Request body must be valid JSON")
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def require_fields(data, fields):
    missing = [f for f in fields if f not in data]
    if missing:
        raise ValidationError(
            "Missing required field(s)", details={"missing": missing}
        )


def validate_username(value):
    if not isinstance(value, str) or not USERNAME_RE.match(value):
        raise ValidationError(
            "Username must be 3-80 characters (letters, digits, underscores only)"
        )


def validate_email(value):
    if not isinstance(value, str) or not EMAIL_RE.match(value):
        raise ValidationError("A valid email address is required")


def validate_password(value):
    if not isinstance(value, str) or len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    if len(value) > 128:
        raise ValidationError("Password must be at most 128 characters long")


def validate_name(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("name is required and must be a non-empty string")
    value = value.strip()
    if len(value) > 120:
        raise ValidationError("name must be at most 120 characters")
    return value


def validate_description(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("description must be a string")
    return value


def parse_pagination():
    default = current_app.config["DEFAULT_PAGE_SIZE"]
    maximum = current_app.config["MAX_PAGE_SIZE"]

    def to_int(name, fallback):
        raw = request.args.get(name)
        if raw is None or raw == "":
            return fallback
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ValidationError(f"{name} must be an integer")

    page = to_int("page", 1)
    per_page = to_int("per_page", default)

    if page < 1:
        raise ValidationError("page must be greater than or equal to 1")
    if per_page < 1:
        raise ValidationError("per_page must be greater than or equal to 1")
    if per_page > maximum:
        raise ValidationError(f"per_page cannot exceed {maximum}")

    return page, per_page
