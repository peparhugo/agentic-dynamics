import functools
import logging
from datetime import datetime, timezone

import jwt
from flask import current_app, g, request, jsonify

from app.models.user import User

logger = logging.getLogger("audit")


class AuthError(Exception):
    status_code = 401

    def __init__(self, message: str, error_type: str = "unauthorized"):
        self.message = message
        self.error_type = error_type


class ForbiddenError(Exception):
    status_code = 403

    def __init__(self, message: str, error_type: str = "forbidden"):
        self.message = message
        self.error_type = error_type


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"],
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token has expired", "token_expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("Invalid token", "token_invalid") from e


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthError("Missing or invalid Authorization header", "no_token")

        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)

        if payload.get("type") != "access":
            raise AuthError("Invalid token type", "invalid_token_type")

        user = User.find_by_id(payload["sub"])
        if not user:
            raise AuthError("User not found", "user_not_found")

        g.current_user = user
        g.token_payload = payload

        logger.info(
            "Authenticated request",
            extra={
                "audit_type": "auth",
                "user_id": user.id,
                "email": user.email,
                "method": request.method,
                "path": request.path,
            },
        )

        return f(*args, **kwargs)

    return decorated


def role_required(*roles: str):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if g.current_user.role not in roles:
                raise ForbiddenError(
                    f"Requires one of {roles} role(s)", "insufficient_permissions"
                )
            return f(*args, **kwargs)

        return decorated

    return decorator


def optional_login(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ", 1)[1]
                payload = decode_token(token)
                if payload.get("type") == "access":
                    user = User.find_by_id(payload["sub"])
                    if user:
                        g.current_user = user
                        g.token_payload = payload
            except AuthError:
                pass
        return f(*args, **kwargs)

    return decorated
