from functools import wraps

from flask import g, request

from .errors import ForbiddenError, UnauthorizedError
from .extensions import db
from .models import User
from .security import decode_access_token


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise UnauthorizedError("Missing or invalid Authorization header")
        token = header.split(" ", 1)[1].strip()
        if not token:
            raise UnauthorizedError("Missing or invalid Authorization header")
        payload = decode_access_token(token)
        user = db.session.get(User, int(payload["sub"]))
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or inactive")
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, "current_user", None) is None:
            raise UnauthorizedError("Authentication required")
        if g.current_user.role != "admin":
            raise ForbiddenError("Administrator privileges required")
        return fn(*args, **kwargs)

    return wrapper
