"""JWT creation/verification and route protection decorators."""
import uuid
from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from ..errors import AuthError, ForbiddenError
from ..models import User


def _make_token(user: User, token_type: str, ttl) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "type": token_type,
        "iss": current_app.config["JWT_ISSUER"],
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"],
                      algorithm=current_app.config["JWT_ALGORITHM"])


def create_access_token(user: User) -> str:
    return _make_token(user, "access", current_app.config["JWT_ACCESS_TOKEN_TTL"])


def create_refresh_token(user: User) -> str:
    return _make_token(user, "refresh", current_app.config["JWT_REFRESH_TOKEN_TTL"])


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
            issuer=current_app.config["JWT_ISSUER"],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired.", code="token_expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token.", code="token_invalid")

    if payload.get("type") != expected_type:
        raise AuthError(f"Expected a {expected_type} token.", code="token_invalid")
    return payload


def _get_bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Missing or malformed Authorization header.",
                        code="token_missing")
    return parts[1]


def _load_current_user(expected_type: str = "access") -> User:
    payload = decode_token(_get_bearer_token(), expected_type)
    user = User.query.get(int(payload["sub"]))
    if user is None:
        raise AuthError("User no longer exists.", code="token_invalid")
    return user


def auth_required(fn):
    """Require a valid access token; sets g.current_user."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.current_user = _load_current_user("access")
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """Require a valid access token belonging to an admin."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _load_current_user("access")
        if user.role != "admin":
            raise ForbiddenError("Admin privileges required.")
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper
