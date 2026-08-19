from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, jsonify, request

from app.extensions import db
from app.models import User


def generate_token(user):
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=current_app.config["JWT_EXPIRATION_MINUTES"]),
    }
    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        user = db.session.get(User, int(payload["sub"]))
        if user is None:
            return jsonify({"error": "User not found"}), 401

        request.current_user = user
        return fn(*args, **kwargs)

    return wrapper
