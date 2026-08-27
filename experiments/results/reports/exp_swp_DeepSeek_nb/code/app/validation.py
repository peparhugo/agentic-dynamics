import re

from .errors import ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_fields(data, required):
    missing = [f for f in required if f not in data or data[f] in (None, "")]
    if missing:
        raise ValidationError(
            "Missing required field(s)",
            details={"fields": missing},
        )


def require_string(data, field, min_length=1, max_length=255, required=True):
    if field not in data:
        if required:
            raise ValidationError("Missing required field", details={"field": field})
        return None
    value = data[field]
    if not isinstance(value, str):
        raise ValidationError("Must be a string", details={"field": field})
    if min_length is not None and len(value) < min_length:
        raise ValidationError(
            "Too short", details={"field": field, "min_length": min_length}
        )
    if max_length is not None and len(value) > max_length:
        raise ValidationError(
            "Too long", details={"field": field, "max_length": max_length}
        )
    return value


def validate_username(username):
    value = require_string({"username": username}, "username", min_length=3, max_length=80)
    if not re.match(r"^[A-Za-z0-9_.-]+$", value):
        raise ValidationError(
            "Username may only contain letters, numbers, '.', '_', and '-'",
            details={"field": "username"},
        )
    return value


def validate_email(email):
    value = require_string({"email": email}, "email", min_length=3, max_length=255)
    if not EMAIL_RE.match(value):
        raise ValidationError("Invalid email address", details={"field": "email"})
    return value


def validate_password(password):
    value = require_string({"password": password}, "password", min_length=8, max_length=128)
    return value


def validate_item_payload(data):
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    name = require_string(data, "name", min_length=1, max_length=120)
    description = require_string(
        data, "description", min_length=0, max_length=5000, required=False
    )
    return {"name": name, "description": description}


def validate_pagination(args):
    page = _parse_int(args.get("page", 1), "page", default=1, minimum=1)
    per_page = _parse_int(
        args.get("per_page", 20), "per_page", default=20, minimum=1
    )
    return page, per_page


def _parse_int(value, field, default, minimum=None, maximum=None):
    if value in (None, ""):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Must be an integer", details={"field": field})
    if minimum is not None and result < minimum:
        raise ValidationError("Out of range", details={"field": field, "minimum": minimum})
    if maximum is not None and result > maximum:
        raise ValidationError("Out of range", details={"field": field, "maximum": maximum})
    return result
