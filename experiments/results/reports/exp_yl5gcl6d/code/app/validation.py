"""Lightweight declarative input validation.

A schema is a dict mapping field name -> Field. `validate(schema, data)` returns
the cleaned data or raises ValidationApiError with per-field details, e.g.:

    {"error": {"code": "validation_error", ...,
               "details": {"fields": {"email": "Not a valid email address."}}}}
"""
import re

from flask import request

from .errors import ValidationApiError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_MISSING = object()


class Field:
    type = None
    type_error = "Invalid type."

    def __init__(self, *, required=True, default=_MISSING, min_length=None,
                 max_length=None, min_value=None, max_value=None, choices=None,
                 strip=True):
        self.required = required
        self.default = default
        self.min_length = min_length
        self.max_length = max_length
        self.min_value = min_value
        self.max_value = max_value
        self.choices = choices
        self.strip = strip

    def clean(self, value):
        """Return cleaned value or raise ValueError(message)."""
        value = self.coerce(value)
        if isinstance(value, str) and self.strip:
            value = value.strip()
        if self.min_length is not None and len(value) < self.min_length:
            raise ValueError(f"Must be at least {self.min_length} characters long.")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError(f"Must be at most {self.max_length} characters long.")
        if self.min_value is not None and value < self.min_value:
            raise ValueError(f"Must be >= {self.min_value}.")
        if self.max_value is not None and value > self.max_value:
            raise ValueError(f"Must be <= {self.max_value}.")
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"Must be one of: {', '.join(map(str, self.choices))}.")
        return value

    def coerce(self, value):
        if self.type is not None and not isinstance(value, self.type):
            raise ValueError(self.type_error)
        return value


class String(Field):
    type = str
    type_error = "Must be a string."


class Integer(Field):
    type_error = "Must be an integer."

    def coerce(self, value):
        # bool is a subclass of int; reject it explicitly.
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(self.type_error)
        return value


class Email(String):
    def clean(self, value):
        value = super().clean(value)
        if not EMAIL_RE.match(value):
            raise ValueError("Not a valid email address.")
        return value.lower()


def validate(schema: dict, data) -> dict:
    if not isinstance(data, dict):
        raise ValidationApiError("Request body must be a JSON object.")

    errors: dict[str, str] = {}
    cleaned: dict = {}

    for name, field in schema.items():
        if name not in data or data[name] is None:
            if field.required:
                errors[name] = "This field is required."
            elif field.default is not _MISSING:
                cleaned[name] = field.default
            continue
        try:
            cleaned[name] = field.clean(data[name])
        except ValueError as exc:
            errors[name] = str(exc)

    unknown = set(data) - set(schema)
    for name in unknown:
        errors[name] = "Unknown field."

    if errors:
        raise ValidationApiError("Input validation failed.",
                                 details={"fields": errors})
    return cleaned


def validate_json(schema: dict) -> dict:
    """Validate the current request's JSON body against a schema."""
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationApiError("Request body must be valid JSON.")
    return validate(schema, data)
