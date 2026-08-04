import hashlib
from datetime import datetime, timedelta, timezone
from functools import wraps
from uuid import uuid4

import jwt
from flask import current_app, g, request

from .errors import APIError
from .models import RefreshToken, User


def _encode_token(user_id, token_type, ttl):
    now = datetime.now(timezone.utc)
    jti = uuid4().hex
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")
    return token, payload


def issue_token_pair(user_id, session):
    access, _ = _encode_token(
        user_id, "access", current_app.config["ACCESS_TOKEN_TTL"]
    )
    refresh, payload = _encode_token(
        user_id, "refresh", current_app.config["REFRESH_TOKEN_TTL"]
    )
    session.add(
        RefreshToken(
            user_id=user_id,
            jti_hash=hash_jti(payload["jti"]),
            expires_at=payload["exp"],
        )
    )
    return {"access_token": access, "refresh_token": refresh, "token_type": "Bearer"}


def hash_jti(jti):
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(
            token, current_app.config["JWT_SECRET"], algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError as exc:
        raise APIError(401, "token_expired", "Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise APIError(401, "invalid_token", "Token is invalid") from exc
    if payload.get("type") != expected_type:
        raise APIError(401, "invalid_token", f"A {expected_type} token is required")
    return payload


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, separator, token = header.partition(" ")
        if not separator or scheme.lower() != "bearer" or not token:
            raise APIError(401, "authentication_required", "Bearer token is required")
        payload = decode_token(token, "access")
        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(401, "invalid_token", "Token is invalid") from exc
        session = current_app.extensions["db_session"]
        user = session.get(User, user_id)
        if user is None:
            raise APIError(401, "invalid_token", "Token user no longer exists")
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped
