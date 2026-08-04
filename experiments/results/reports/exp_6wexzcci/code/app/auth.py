"""JWT-based authentication: token issuance, verification, and route guard."""
import datetime as dt
import functools
import hashlib
import hmac
import secrets
import uuid

import jwt
from flask import current_app, g, request

from .errors import AuthError

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


def _make_token(user_id: int, token_type: str, ttl_seconds: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + dt.timedelta(seconds=ttl_seconds),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def issue_tokens(user_id: int) -> dict:
    cfg = current_app.config
    return {
        "access_token": _make_token(user_id, "access", cfg["JWT_ACCESS_TTL_SECONDS"]),
        "refresh_token": _make_token(user_id, "refresh", cfg["JWT_REFRESH_TTL_SECONDS"]),
        "token_type": "Bearer",
        "expires_in": cfg["JWT_ACCESS_TTL_SECONDS"],
    }


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired.", error_code="token_expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token.", error_code="token_invalid")
    if payload.get("type") != expected_type:
        raise AuthError(
            f"Expected a {expected_type} token.", error_code="wrong_token_type"
        )
    return payload


def _bearer_token() -> str:
    header = request.headers.get("Authorization", "")
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Missing or malformed Authorization header.",
                        error_code="missing_token")
    return parts[1]


def require_auth(fn):
    """Decorator: route requires a valid access token. Sets g.current_user_id."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        payload = decode_token(_bearer_token(), "access")
        g.current_user_id = int(payload["sub"])
        return fn(*args, **kwargs)

    return wrapper
