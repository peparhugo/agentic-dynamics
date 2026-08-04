"""Declarative request validation without external dependencies.

Usage:
    data = validate(request.get_json(silent=True), {
        "title": Field(str, required=True, max_length=200),
        "tags": Field(list, item_type=str, default=[]),
    })
Raises ValidationFailure (422) with per-field error details.
"""
import re

from .errors import ValidationFailure

_MISSING = object()


class Field:
    def __init__(self, type_, required=False, default=_MISSING, min_length=None,
                 max_length=None, pattern=None, item_type=None, choices=None,
                 min_value=None, max_value=None):
        self.type = type_
        self.required = required
        self.default = default
        self.min_length = min_length
        self.max_length = max_length
        self.pattern = re.compile(pattern) if pattern else None
        self.item_type = item_type
        self.choices = choices
        self.min_value = min_value
        self.max_value = max_value

    def check(self, name, value, errors):
        if not isinstance(value, self.type) or (self.type is not bool and isinstance(value, bool)):
            errors[name] = f"must be of type {self.type.__name__}"
            return None
        if isinstance(value, str):
            value = value.strip()
            if self.min_length is not None and len(value) < self.min_length:
                errors[name] = f"must be at least {self.min_length} characters"
                return None
            if self.max_length is not None and len(value) > self.max_length:
                errors[name] = f"must be at most {self.max_length} characters"
                return None
            if self.pattern and not self.pattern.match(value):
                errors[name] = "has an invalid format"
                return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if self.min_value is not None and value < self.min_value:
                errors[name] = f"must be >= {self.min_value}"
                return None
            if self.max_value is not None and value > self.max_value:
                errors[name] = f"must be <= {self.max_value}"
                return None
        if isinstance(value, list):
            if self.max_length is not None and len(value) > self.max_length:
                errors[name] = f"must have at most {self.max_length} items"
                return None
            if self.item_type is not None:
                for i, item in enumerate(value):
                    if not isinstance(item, self.item_type):
                        errors[name] = f"item {i} must be of type {self.item_type.__name__}"
                        return None
        if self.choices is not None and value not in self.choices:
            errors[name] = f"must be one of: {', '.join(map(str, self.choices))}"
            return None
        return value


def validate(payload, schema, partial=False):
    if payload is None or not isinstance(payload, dict):
        raise ValidationFailure("Request body must be a JSON object.")

    errors = {}
    unknown = set(payload) - set(schema)
    for key in unknown:
        errors[key] = "unknown field"

    result = {}
    for name, field in schema.items():
        if name not in payload:
            if partial:
                continue
            if field.required:
                errors[name] = "is required"
            elif field.default is not _MISSING:
                result[name] = field.default
            continue
        value = field.check(name, payload[name], errors)
        if name not in errors:
            result[name] = value

    if errors:
        raise ValidationFailure("Input validation failed.", details={"fields": errors})
    return result


def parse_pagination(args, default_size, max_size):
    """Parse ?page=&per_page= query params. Raises 422 on bad values."""
    errors = {}
    try:
        page = int(args.get("page", 1))
        if page < 1:
            errors["page"] = "must be >= 1"
    except (TypeError, ValueError):
        errors["page"] = "must be an integer"
        page = 1
    try:
        per_page = int(args.get("per_page", default_size))
        if per_page < 1:
            errors["per_page"] = "must be >= 1"
        elif per_page > max_size:
            errors["per_page"] = f"must be <= {max_size}"
    except (TypeError, ValueError):
        errors["per_page"] = "must be an integer"
        per_page = default_size
    if errors:
        raise ValidationFailure("Invalid pagination parameters.", details={"fields": errors})
    return page, per_page
