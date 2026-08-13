"""
JWT authentication helpers for the task management API.

Passwords are hashed with werkzeug's PBKDF2-based helpers; auth tokens are
signed JWTs (HS256) carrying the user id and username, verified on every
protected request.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

TOKEN_TTL_SECONDS = 3600


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


def create_token(user: dict, secret_key: str) -> str:
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "exp": datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict | None:
    try:
        payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload


def require_auth(app):
    """Decorator factory: verifies the Bearer JWT and looks up the user."""

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "missing or invalid authorization header"}), 401
            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token, app.config["SECRET_KEY"])
            if payload is None:
                return jsonify({"error": "invalid or expired token"}), 401
            user = app.user_repository.get_by_id(payload["sub"])
            if user is None:
                return jsonify({"error": "invalid or expired token"}), 401
            return f(user, *args, **kwargs)

        return decorated

    return decorator
