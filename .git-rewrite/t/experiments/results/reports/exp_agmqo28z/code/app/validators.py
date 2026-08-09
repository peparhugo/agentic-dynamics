import re
from app.errors import ValidationError


def validate_required(data, fields):
    missing = [f for f in fields if f not in data or not data[f]]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")


def validate_username(username):
    if not username or not isinstance(username, str):
        raise ValidationError("Username is required")
    username = username.strip()
    if len(username) < 3:
        raise ValidationError("Username must be at least 3 characters")
    if len(username) > 80:
        raise ValidationError("Username must be at most 80 characters")
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        raise ValidationError(
            "Username must contain only letters, numbers, and underscores"
        )
    return username


def validate_email(email):
    if not email or not isinstance(email, str):
        raise ValidationError("Email is required")
    email = email.strip()
    if len(email) > 120:
        raise ValidationError("Email must be at most 120 characters")
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    if not re.match(pattern, email):
        raise ValidationError("Invalid email format")
    return email


def validate_password(password):
    if not password or not isinstance(password, str):
        raise ValidationError("Password is required")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    if len(password) > 128:
        raise ValidationError("Password must be at most 128 characters")
    return password


def validate_pagination(page, per_page):
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = 20
    if per_page < 1:
        per_page = 20
    if per_page > 100:
        per_page = 100

    return page, per_page


def validate_registration(data):
    validate_required(data, ["username", "email", "password"])
    username = validate_username(data["username"])
    email = validate_email(data["email"])
    password = validate_password(data["password"])
    return {"username": username, "email": email, "password": password}


def validate_login(data):
    validate_required(data, ["username_or_email", "password"])
    credentials = data["username_or_email"].strip()
    password = data["password"]
    if not credentials:
        raise ValidationError("Username or email is required")
    if not password:
        raise ValidationError("Password is required")
    return {"username_or_email": credentials, "password": password}


def validate_user_update(data):
    if not data:
        raise ValidationError("No fields to update")
    validated = {}
    if "username" in data and data["username"] is not None:
        validated["username"] = validate_username(data["username"])
    if "email" in data and data["email"] is not None:
        validated["email"] = validate_email(data["email"])
    if "password" in data and data["password"] is not None:
        validated["password"] = validate_password(data["password"])
    if not validated:
        raise ValidationError(
            "At least one field is required: username, email, password"
        )
    return validated
