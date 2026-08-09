from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import request, g, current_app

from app.models.user import User


def create_token(user_id, role="user"):
    payload = {
        "sub": user_id,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(hours=current_app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["SECRET_KEY"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def get_current_user():
    return g.get("current_user")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization")
        if not header or not header.startswith("Bearer "):
            return {"error": "Missing or invalid Authorization header"}, 401

        try:
            payload = decode_token(header.split(" ", 1)[1])
        except jwt.ExpiredSignatureError:
            return {"error": "Token has expired"}, 401
        except jwt.InvalidTokenError:
            return {"error": "Invalid token"}, 401

        user = User.get_by_id(payload["sub"])
        if not user:
            return {"error": "User not found"}, 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def require_role(*roles):

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                return {"error": "Authentication required"}, 401
            if user.role not in roles:
                return {"error": "Insufficient permissions"}, 403
            return f(*args, **kwargs)

        return decorated

    return decorator
