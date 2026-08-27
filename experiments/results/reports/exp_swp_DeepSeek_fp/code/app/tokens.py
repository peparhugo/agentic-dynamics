from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app


def _secret():
    return current_app.config["JWT_SECRET_KEY"]


def _algorithm():
    return current_app.config["JWT_ALGORITHM"]


def create_access_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=current_app.config["ACCESS_TOKEN_EXPIRE_MINUTES"]),
    }
    return jwt.encode(payload, _secret(), algorithm=_algorithm())


def create_refresh_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=current_app.config["REFRESH_TOKEN_EXPIRE_DAYS"]),
    }
    return jwt.encode(payload, _secret(), algorithm=_algorithm())


def decode_token(token):
    return jwt.decode(token, _secret(), algorithms=[_algorithm()])
