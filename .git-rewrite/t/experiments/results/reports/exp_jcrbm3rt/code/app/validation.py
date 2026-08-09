"""Lightweight declarative input validation.

A schema is a dict of field name -> spec dict. Supported spec keys:

    type       python type (str, int, bool, ...)
    required   bool (default False)
    min_length / max_length   for strings
    min / max                 for numbers
    pattern    compiled regex or regex string (full match)
    choices    iterable of allowed values
    strip      strip whitespace on strings (default True)

`validate(data, schema)` returns the cleaned payload or raises
ValidationError with a per-field `details` dict.
"""
import re

from flask import request

from .errors import ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def json_body():
    """Return the request JSON body or raise a ValidationError."""
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data


def validate(data, schema):
    errors = {}
    cleaned = {}

    unknown = set(data) - set(schema)
    for field in unknown:
        errors[field] = "unknown field"

    for field, spec in schema.items():
        required = spec.get("required", False)
        if field not in data or data[field] is None:
            if required:
                errors[field] = "this field is required"
            continue

        value = data[field]
        ftype = spec.get("type")

        # bool is a subclass of int; reject bools for int fields explicitly.
        if ftype is int and isinstance(value, bool):
            errors[field] = "must be of type int"
            continue
        if ftype is not None and not isinstance(value, ftype):
            errors[field] = f"must be of type {ftype.__name__}"
            continue

        if isinstance(value, str) and spec.get("strip", True):
            value = value.strip()

        if isinstance(value, str):
            if required and not value:
                errors[field] = "must not be empty"
                continue
            if "min_length" in spec and len(value) < spec["min_length"]:
                errors[field] = f"must be at least {spec['min_length']} characters"
                continue
            if "max_length" in spec and len(value) > spec["max_length"]:
                errors[field] = f"must be at most {spec['max_length']} characters"
                continue
            pattern = spec.get("pattern")
            if pattern is not None:
                if isinstance(pattern, str):
                    pattern = re.compile(pattern)
                if not pattern.fullmatch(value):
                    errors[field] = spec.get("pattern_message", "invalid format")
                    continue

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "min" in spec and value < spec["min"]:
                errors[field] = f"must be >= {spec['min']}"
                continue
            if "max" in spec and value > spec["max"]:
                errors[field] = f"must be <= {spec['max']}"
                continue

        if "choices" in spec and value not in spec["choices"]:
            errors[field] = f"must be one of: {', '.join(map(str, spec['choices']))}"
            continue

        cleaned[field] = value

    if errors:
        raise ValidationError("Invalid input", details=errors)
    return cleaned
