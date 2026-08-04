import re

from flask import request


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ValidationError(Exception):
    def __init__(self, errors):
        super().__init__("Invalid request data")
        self.errors = errors


def json_body():
    if not request.is_json:
        raise ValidationError({"body": "Content-Type must be application/json"})
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError({"body": "A JSON object is required"})
    return data


def validate_credentials(data, require_email=True):
    errors = {}
    email = data.get("email")
    password = data.get("password")
    if require_email and (not isinstance(email, str) or not EMAIL_RE.fullmatch(email.strip())):
        errors["email"] = "A valid email address is required"
    if not isinstance(password, str) or not password:
        errors["password"] = "Password is required"
    if errors:
        raise ValidationError(errors)
    return email.strip().lower(), password


def validate_registration(data):
    email, password = validate_credentials(data)
    if len(password) < 8:
        raise ValidationError({"password": "Password must be at least 8 characters"})
    if len(email) > 255:
        raise ValidationError({"email": "Email must be at most 255 characters"})
    return email, password


def validate_item(data, partial=False):
    allowed = {"name", "description"}
    errors = {}
    unknown = set(data) - allowed
    if unknown:
        errors["body"] = f"Unknown fields: {', '.join(sorted(unknown))}"
    if not partial or "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "Name is required"
        elif len(name.strip()) > 120:
            errors["name"] = "Name must be at most 120 characters"
    if "description" in data:
        description = data["description"]
        if description is not None and not isinstance(description, str):
            errors["description"] = "Description must be a string or null"
    if partial and not data:
        errors["body"] = "At least one field is required"
    if errors:
        raise ValidationError(errors)
    return {
        key: value.strip() if key == "name" else value
        for key, value in data.items()
        if key in allowed
    }


def pagination_args():
    errors = {}
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            raise ValueError
    except (TypeError, ValueError):
        errors["page"] = "Page must be a positive integer"
        page = 1
    try:
        per_page = int(request.args.get("per_page", 20))
        if not 1 <= per_page <= 100:
            raise ValueError
    except (TypeError, ValueError):
        errors["per_page"] = "Per page must be between 1 and 100"
        per_page = 20
    if errors:
        raise ValidationError(errors)
    return page, per_page
