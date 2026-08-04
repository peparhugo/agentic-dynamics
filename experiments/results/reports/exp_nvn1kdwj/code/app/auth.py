from datetime import datetime, timezone
from http import HTTPStatus

from flask import request
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User
from app.errors import UnauthorizedError, ConflictError


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password, password_hash):
    return check_password_hash(password_hash, password)


def authenticate_user(username, password):
    user = User.query.filter_by(username=username).first()
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError(message="Invalid username or password.")
    if not user.is_active:
        raise UnauthorizedError(message="Account is deactivated.")
    return user


def generate_tokens(user):
    additional_claims = {"role": user.role, "email": user.email}
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims=additional_claims,
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
    )
    return access_token, refresh_token


def get_current_user():
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
    verify_jwt_in_request()
    user_id = get_jwt_identity()
    if user_id is None:
        raise UnauthorizedError()
    user = db.session.get(User, int(user_id))
    if not user or not user.is_active:
        raise UnauthorizedError(message="User not found or inactive.")
    return user


def get_current_user_or_none():
    from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            return db.session.get(User, int(user_id))
    except Exception:
        pass
    return None


def register_user(username, email, password, role="user"):
    if User.query.filter_by(username=username).first():
        raise ConflictError(message=f"Username '{username}' is already taken.")
    if User.query.filter_by(email=email).first():
        raise ConflictError(message=f"Email '{email}' is already registered.")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return user


def require_role(role):
    from functools import wraps
    from flask_jwt_extended import verify_jwt_in_request, get_jwt
    from app.errors import ForbiddenError

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") != role and claims.get("role") != "admin":
                raise ForbiddenError(f"Role '{role}' or 'admin' is required.")
            return fn(*args, **kwargs)
        return wrapper
    return decorator
