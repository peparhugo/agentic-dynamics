from functools import wraps
from flask import request, g
from marshmallow import ValidationError

from ..utils.token import decode_token, create_access_token, create_refresh_token


def require_auth(f):
    def _require_auth(*args, **kwargs):
        return _authenticate(f, required=True)(*args, **kwargs)
    return _require_auth


def optional_auth(f):
    def _optional_auth(*args, **kwargs):
        return _authenticate(f, required=False)(*args, **kwargs)
    return _optional_auth


def _authenticate(view_func, required):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        g.current_user = None
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            if required:
                return {"error": "Missing or invalid Authorization header", "code": "UNAUTHORIZED"}, 401
            return view_func(*args, **kwargs)

        token = auth_header[7:]
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                return {"error": "Invalid token type", "code": "INVALID_TOKEN_TYPE"}, 401
            g.current_user_id = payload["sub"]
            g.current_user_role = payload["role"]
        except Exception:
            if required:
                return {"error": "Invalid or expired token", "code": "INVALID_TOKEN"}, 401
            return view_func(*args, **kwargs)

        return view_func(*args, **kwargs)

    return wrapper
