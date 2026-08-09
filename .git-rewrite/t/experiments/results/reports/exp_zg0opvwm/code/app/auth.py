import functools
import time

import jwt
from flask import current_app, g, request

from app.errors import APIError

_rate_limit_store = {}


def generate_token(user_id, token_type="access"):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    if token_type == "access":
        expires_delta = timedelta(
            seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
        )
    else:
        expires_delta = timedelta(
            seconds=current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]
        )

    payload = {
        "sub": user_id,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_token(token, token_type=None):
    try:
        payload = jwt.decode(
            token,
            current_app.config["SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
        if token_type and payload.get("type") != token_type:
            raise APIError("Invalid token type", 401)
        return payload
    except jwt.ExpiredSignatureError:
        raise APIError("Token has expired", 401)
    except jwt.InvalidTokenError:
        raise APIError("Invalid token", 401)


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        from app.models import User

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise APIError("Missing or invalid Authorization header", 401)

        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token, token_type="access")
        user = User.query.get(payload["sub"])
        if not user:
            raise APIError("User not found", 401)

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def check_rate_limit(key, max_attempts, window_seconds):
    now = time.time()
    store = _rate_limit_store

    if key not in store:
        store[key] = []

    store[key] = [t for t in store[key] if t > now - window_seconds]

    if len(store[key]) >= max_attempts:
        raise APIError("Too many requests. Please try again later.", 429)

    store[key].append(now)


def clear_rate_limits():
    _rate_limit_store.clear()
