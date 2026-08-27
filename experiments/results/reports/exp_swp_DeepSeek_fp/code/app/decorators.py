from functools import wraps

import jwt
from flask import g, request

from .errors import APIError
from .extensions import db
from .models import User
from .tokens import decode_token


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise APIError("Missing or invalid Authorization header", 401, "unauthorized")
        token = header[len("Bearer "):].strip()
        if not token:
            raise APIError("Missing token", 401, "unauthorized")
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            raise APIError("Token has expired", 401, "token_expired")
        except jwt.InvalidTokenError:
            raise APIError("Invalid token", 401, "invalid_token")
        if payload.get("type") != "access":
            raise APIError("Invalid token type", 401, "invalid_token_type")
        sub = payload.get("sub")
        if sub is None:
            raise APIError("Invalid token", 401, "invalid_token")
        user = db.session.get(User, int(sub))
        if user is None:
            raise APIError("User no longer exists", 401, "user_not_found")
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper
