"""Lightweight request body validation (no external deps).

Usage:
    data = validate_json({
        "email": {"type": str, "required": True, "format": "email"},
        "title": {"type": str, "required": True, "max_length": 200},
    })
Unknown fields are rejected. Raises ValidationError with per-field details.
"""
import re

from flask import request

from .errors import ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_json(schema: dict) -> dict:
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        raise ValidationError("Request body must be a JSON object.")

    errors = {}
    cleaned = {}

    for field in body:
        if field not in schema:
            errors[field] = "Unknown field."
    for field, rules in schema.items():
        present = field in body
        if not present:
            if rules.get("required"):
                errors[field] = "This field is required."
            elif "default" in rules:
                cleaned[field] = rules["default"]
            continue
        value = body[field]
        expected = rules.get("type")
        if expected is not None and not isinstance(value, expected):
            errors[field] = f"Expected {expected.__name__}."
            continue
        if isinstance(value, str):
            if rules.get("strip", True):
                value = value.strip()
            min_len = rules.get("min_length")
            max_len = rules.get("max_length")
            if min_len is not None and len(value) < min_len:
                errors[field] = f"Must be at least {min_len} characters."
                continue
            if max_len is not None and len(value) > max_len:
                errors[field] = f"Must be at most {max_len} characters."
                continue
            if rules.get("format") == "email" and not EMAIL_RE.match(value):
                errors[field] = "Must be a valid email address."
                continue
        cleaned[field] = value

    if errors:
        raise ValidationError(details={"fields": errors})
    return cleaned


def parse_pagination(default_per_page: int, max_per_page: int):
    """Parse and bound `page` and `per_page` query params."""
    errors = {}
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            raise ValueError
    except ValueError:
        errors["page"] = "Must be a positive integer."
        page = 1
    try:
        per_page = int(request.args.get("per_page", default_per_page))
        if per_page < 1:
            raise ValueError
    except ValueError:
        errors["per_page"] = "Must be a positive integer."
        per_page = default_per_page
    if errors:
        raise ValidationError(details={"fields": errors})
    return page, min(per_page, max_per_page)
