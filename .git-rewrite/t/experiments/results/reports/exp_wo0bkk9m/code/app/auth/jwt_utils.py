"""JWT creation/verification and route protection decorators."""
import uuid
from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from ..errors import ForbiddenError, UnauthorizedError
from ..models import User


def _create_token(user: User, token_type: str, expires_delta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "type": token_type,
        "role": user.role,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def create_access_token(user: User) -> str:
    return _create_token(user, "access", current_app.config["JWT_ACCESS_TOKEN_EXPIRES"])


def create_refresh_token(user: User) -> str:
    return _create_token(user, "refresh", current_app.config["JWT_REFRESH_TOKEN_EXPIRES"])


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired.", code="token_expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token.", code="token_invalid")


def _get_token_from_header() -> str:
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedError(
            "Missing or malformed Authorization header. Expected 'Bearer <token>'.",
            code="token_missing",
        )
    return parts[1]


def _load_user_from_token(expected_type: str) -> User:
    payload = decode_token(_get_token_from_header())
    if payload.get("type") != expected_type:
        raise UnauthorizedError(
            f"Expected a {expected_type} token.", code="wrong_token_type"
        )
    user = User.query.get(int(payload["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("User no longer exists or is inactive.",
                                code="user_inactive")
    return user


def jwt_required(fn):
    """Require a valid access token; sets g.current_user."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.current_user = _load_user_from_token("access")
        return fn(*args, **kwargs)

    return wrapper


def refresh_token_required(fn):
    """Require a valid refresh token; sets g.current_user."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.current_user = _load_user_from_token("refresh")
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    """Require the authenticated user to have one of the given roles."""

    def decorator(fn):
        @wraps(fn)
        @jwt_required
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                raise ForbiddenError("You do not have permission to access this resource.")
            return fn(*args, **kwargs)

        return wrapper

    return decorator
