from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .extensions import db
from .models import User


def encode_access_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + current_app.config["JWT_EXPIRATION_DELTA"],
        "type": "access",
    }
    return jwt.encode(
        payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"]
    )


def decode_access_token(token):
    return jwt.decode(
        token, current_app.config["SECRET_KEY"], algorithms=[current_app.config["JWT_ALGORITHM"]]
    )


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify(error="Missing or malformed Authorization header"), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_access_token(token)
            user_id = int(payload["sub"])
        except jwt.ExpiredSignatureError:
            return jsonify(error="Token has expired"), 401
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            return jsonify(error="Invalid or expired token"), 401

        user = db.session.get(User, user_id)
        if user is None:
            return jsonify(error="User associated with token no longer exists"), 401

        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


def admin_required(f):
    @wraps(f)
    @token_required
    def wrapper(*args, **kwargs):
        if g.current_user.role != "admin":
            return jsonify(error="Admin privileges required"), 403
        return f(*args, **kwargs)

    return wrapper
