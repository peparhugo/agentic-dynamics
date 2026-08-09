"""JWT authentication: token issuing/verification and route protection."""
import functools
import uuid
from datetime import datetime, timezone

import jwt
from flask import current_app, g, request

from .db import get_db
from .errors import AuthError


def _now():
    return datetime.now(timezone.utc)


def issue_token(user_id: int, token_type: str) -> str:
    cfg = current_app.config
    ttl = cfg["JWT_ACCESS_TTL"] if token_type == "access" else cfg["JWT_REFRESH_TTL"]
    now = _now()
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iss": cfg["JWT_ISSUER"],
        "iat": now,
        "exp": now + ttl,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, cfg["SECRET_KEY"], algorithm=cfg["JWT_ALGORITHM"])


def issue_token_pair(user_id: int) -> dict:
    return {
        "access_token": issue_token(user_id, "access"),
        "refresh_token": issue_token(user_id, "refresh"),
        "token_type": "Bearer",
        "expires_in": int(current_app.config["JWT_ACCESS_TTL"].total_seconds()),
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
        raise AuthError("Token has expired", code="token_expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token", code="token_invalid")

    if payload.get("type") != expected_type:
        raise AuthError(f"Expected a {expected_type} token", code="token_invalid")
    return payload


def _bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Missing or malformed Authorization header",
                        code="token_missing")
    return parts[1]


def require_auth(fn):
    """Protect a route. Loads the user into g.current_user."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        payload = decode_token(_bearer_token(), expected_type="access")
        db = get_db()
        user = db.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?",
            (int(payload["sub"]),),
        ).fetchone()
        if user is None:
            raise AuthError("User no longer exists", code="token_invalid")
        g.current_user = dict(user)
        g.jwt_payload = payload
        return fn(*args, **kwargs)

    return wrapper
