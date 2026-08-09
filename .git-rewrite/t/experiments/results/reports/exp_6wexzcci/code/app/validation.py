"""Lightweight declarative validation for JSON request bodies."""
import re

from flask import request

from .errors import ValidationAPIError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Field:
    def __init__(self, type_=str, required=True, min_length=None, max_length=None,
                 pattern=None, pattern_message=None, strip=True):
        self.type_ = type_
        self.required = required
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = pattern
        self.pattern_message = pattern_message
        self.strip = strip

    def validate(self, name, value, errors):
        if value is None:
            if self.required:
                errors[name] = "This field is required."
            return None
        if not isinstance(value, self.type_) or isinstance(value, bool) and self.type_ is int:
            errors[name] = f"Must be of type {self.type_.__name__}."
            return None
        if isinstance(value, str) and self.strip:
            value = value.strip()
        if self.min_length is not None and len(value) < self.min_length:
            errors[name] = f"Must be at least {self.min_length} characters long."
            return None
        if self.max_length is not None and len(value) > self.max_length:
            errors[name] = f"Must be at most {self.max_length} characters long."
            return None
        if self.pattern is not None and not self.pattern.match(value):
            errors[name] = self.pattern_message or "Invalid format."
            return None
        return value


def validate_json(schema: dict) -> dict:
    """Validate request JSON body against schema; raise 422 with per-field details."""
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        raise ValidationAPIError("Request body must be a JSON object.")

    errors = {}
    unknown = set(data) - set(schema)
    for key in unknown:
        errors[key] = "Unknown field."

    cleaned = {}
    for name, field in schema.items():
        value = field.validate(name, data.get(name), errors)
        if name not in errors and (name in data or field.required):
            cleaned[name] = value

    if errors:
        raise ValidationAPIError("Validation failed.", details=errors)
    return cleaned


# Reusable schemas
REGISTER_SCHEMA = {
    "email": Field(str, max_length=254, pattern=EMAIL_RE,
                   pattern_message="Must be a valid email address."),
    "password": Field(str, min_length=8, max_length=128, strip=False),
}

LOGIN_SCHEMA = {
    "email": Field(str, max_length=254),
    "password": Field(str, max_length=128, strip=False),
}

REFRESH_SCHEMA = {
    "refresh_token": Field(str, max_length=4096),
}

ITEM_CREATE_SCHEMA = {
    "name": Field(str, min_length=1, max_length=120),
    "description": Field(str, required=False, max_length=2000),
}

ITEM_UPDATE_SCHEMA = {
    "name": Field(str, required=False, min_length=1, max_length=120),
    "description": Field(str, required=False, max_length=2000),
}
