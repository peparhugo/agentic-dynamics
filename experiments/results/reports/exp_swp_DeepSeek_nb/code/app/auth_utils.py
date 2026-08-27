import json
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from .errors import AuthenticationError, AuthorizationError, NotFoundError
from .extensions import db
from .models import RefreshToken, User, utcnow


def _encode_token(user_id, token_type, expires_delta, jti=None):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if jti:
        payload["jti"] = jti
    return jwt.encode(
        payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"]
    )


def create_access_token(user_id):
    expires = current_app.config["ACCESS_TOKEN_EXPIRES"]
    return _encode_token(user_id, "access", timedelta(seconds=expires))


def create_refresh_token(user_id):
    expires = current_app.config["REFRESH_TOKEN_EXPIRES"]
    jti = uuid.uuid4().hex
    expires_at = utcnow() + timedelta(seconds=expires)
    record = RefreshToken(user_id=user_id, jti=jti, expires_at=expires_at)
    return record, _encode_token(user_id, "refresh", timedelta(seconds=expires), jti=jti)


def _decode_token(token, expected_type=None):
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")
    if expected_type is not None and payload.get("type") != expected_type:
        raise AuthenticationError("Invalid token type")
    return payload


def get_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise AuthenticationError("Missing or malformed Authorization header")
    token = auth_header[7:].strip()
    if not token:
        raise AuthenticationError("Missing bearer token")
    return token


def load_current_user():
    token = get_bearer_token()
    payload = _decode_token(token, expected_type="access")
    try:
        user = db.session.get(User, int(payload["sub"]))
    except (ValueError, KeyError):
        raise AuthenticationError("Invalid token")
    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthorizationError("User account is disabled")
    g.current_user = user
    g.token_payload = payload
    return user


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        load_current_user()
        return fn(*args, **kwargs)
    return wrapper


def get_current_user_or_none():
    try:
        return load_current_user()
    except (AuthenticationError, AuthorizationError):
        return None
