"""JWT authentication: token issuing/verification and route protection."""
import datetime as dt
import functools
import uuid

import jwt
from flask import current_app, g, request

from .db import get_db
from .errors import AuthenticationError


def _now():
    return dt.datetime.now(dt.timezone.utc)


def issue_token(user_id: int, token_type: str) -> str:
    cfg = current_app.config
    ttl = (
        cfg["JWT_ACCESS_TTL_SECONDS"]
        if token_type == "access"
        else cfg["JWT_REFRESH_TTL_SECONDS"]
    )
    now = _now()
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iss": cfg["JWT_ISSUER"],
        "iat": now,
        "exp": now + dt.timedelta(seconds=ttl),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, cfg["SECRET_KEY"], algorithm=cfg["JWT_ALGORITHM"])


def issue_token_pair(user_id: int) -> dict:
    return {
        "access_token": issue_token(user_id, "access"),
        "refresh_token": issue_token(user_id, "refresh"),
        "token_type": "Bearer",
        "expires_in": current_app.config["JWT_ACCESS_TTL_SECONDS"],
    }


def decode_token(token: str, expected_type: str) -> dict:
    cfg = current_app.config
    try:
        payload = jwt.decode(
            token,
            cfg["SECRET_KEY"],
            algorithms=[cfg["JWT_ALGORITHM"]],
            issuer=cfg["JWT_ISSUER"],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired.", code="token_expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token.", code="token_invalid")
    if payload.get("type") != expected_type:
        raise AuthenticationError(
            f"Expected a {expected_type} token.", code="wrong_token_type"
        )
    return payload


def _extract_bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError(
            "Missing or malformed Authorization header. Expected 'Bearer <token>'."
        )
    return parts[1]


def load_user(user_id: int):
    return get_db().execute(
        "SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()


def require_auth(fn):
    """Decorator: require a valid access token; sets g.current_user."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        payload = decode_token(token, expected_type="access")
        user = load_user(int(payload["sub"]))
        if user is None:
            raise AuthenticationError("User no longer exists.", code="unknown_user")
        g.current_user = user
        g.jwt_payload = payload
        return fn(*args, **kwargs)

    return wrapper
