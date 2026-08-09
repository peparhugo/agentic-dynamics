"""JWT authentication: token issuing/verification and route guards."""
import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app, g, request

from .errors import AuthError, ForbiddenError


def _make_token(user, token_type, ttl_seconds):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "role": user["role"],
        "type": token_type,
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"],
                      algorithm=current_app.config["JWT_ALGORITHM"])


def issue_tokens(user):
    cfg = current_app.config
    return {
        "access_token": _make_token(user, "access", cfg["JWT_ACCESS_TTL_SECONDS"]),
        "refresh_token": _make_token(user, "refresh", cfg["JWT_REFRESH_TTL_SECONDS"]),
        "token_type": "Bearer",
        "expires_in": cfg["JWT_ACCESS_TTL_SECONDS"],
    }


def decode_token(token, expected_type="access"):
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired.", code="token_expired")
    except jwt.InvalidTokenError:
        raise AuthError("Token is invalid.", code="token_invalid")
    if payload.get("type") != expected_type:
        raise AuthError(f"Expected a {expected_type} token.", code="wrong_token_type")
    return payload


def _bearer_token():
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Missing or malformed Authorization header.",
                        code="missing_token")
    return parts[1]


def auth_required(fn=None, *, roles=None):
    """Guard a route. Sets g.current_user. Optionally enforce roles."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            payload = decode_token(_bearer_token(), expected_type="access")
            store = current_app.extensions["store"]
            user = store.get_user(int(payload["sub"]))
            if user is None:
                raise AuthError("User no longer exists.", code="user_not_found")
            if roles and user["role"] not in roles:
                raise ForbiddenError("Insufficient permissions.")
            g.current_user = user
            return func(*args, **kwargs)
        return wrapper

    if fn is not None:  # used as @auth_required without parentheses
        return decorator(fn)
    return decorator
