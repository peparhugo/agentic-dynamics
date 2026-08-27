import json
import re

from flask import request

from .errors import APIError, ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MIN_PASSWORD_LENGTH = 8
MAX_EMAIL_LENGTH = 255
MAX_NAME_LENGTH = 255
MAX_DESCRIPTION_LENGTH = 10000


def _require_object(data):
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")


def get_json_body():
    raw = request.get_data(as_text=True) or ""
    if not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        raise APIError(
            "Request body is not valid JSON.", status_code=400, code="bad_request"
        )
    return parsed


def validate_email(email):
    errors = {}
    if not isinstance(email, str):
        errors["email"] = "Email is required and must be a string."
    elif not email.strip():
        errors["email"] = "Email is required."
    elif len(email) > MAX_EMAIL_LENGTH:
        errors["email"] = f"Email must be at most {MAX_EMAIL_LENGTH} characters."
    elif not EMAIL_RE.match(email):
        errors["email"] = "Email address is not valid."
    return errors


def validate_password(password):
    errors = {}
    if not isinstance(password, str):
        errors["password"] = "Password is required and must be a string."
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = (
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )
    return errors


def validate_register(data):
    _require_object(data)
    errors = {}
    errors.update(validate_email(data.get("email")))
    errors.update(validate_password(data.get("password")))
    return errors


def validate_login(data):
    _require_object(data)
    errors = {}
    if not isinstance(data.get("email"), str) or not data.get("email").strip():
        errors["email"] = "Email is required."
    if not isinstance(data.get("password"), str) or not data.get("password"):
        errors["password"] = "Password is required."
    return errors


def validate_item(data, partial=False):
    _require_object(data)
    errors = {}

    if "name" in data or not partial:
        name = data.get("name")
        if not isinstance(name, str):
            errors["name"] = "Name is required and must be a string."
        elif not name.strip():
            errors["name"] = "Name is required and must not be blank."
        elif len(name) > MAX_NAME_LENGTH:
            errors["name"] = f"Name must be at most {MAX_NAME_LENGTH} characters."

    if "description" in data:
        description = data["description"]
        if description is not None and not isinstance(description, str):
            errors["description"] = "Description must be a string or null."
        elif isinstance(description, str) and len(description) > MAX_DESCRIPTION_LENGTH:
            errors["description"] = (
                f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters."
            )

    if not data and partial:
        errors["body"] = "At least one field must be provided for update."

    return errors


def raise_for_errors(errors):
    if errors:
        raise ValidationError(fields=errors)
