from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, jsonify, request

from .extensions import db
from .models import User


def generate_token(user):
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + current_app.config["JWT_EXPIRATION"],
    }
    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return jsonify({"error": "Token is missing"}), 401

        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET_KEY"],
                algorithms=[current_app.config["JWT_ALGORITHM"]],
            )
            user_id = int(payload["sub"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return jsonify({"error": "Token is invalid"}), 401

        current_user = db.session.get(User, user_id)
        if current_user is None:
            return jsonify({"error": "User not found"}), 401

        return f(current_user, *args, **kwargs)

    return decorated


def parse_datetime(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    candidates = [value.replace("Z", "+00:00")]
    if " " in value:
        candidates.append(value.replace(" ", "+", 1))
    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except (ValueError, AttributeError):
            continue
    return None
