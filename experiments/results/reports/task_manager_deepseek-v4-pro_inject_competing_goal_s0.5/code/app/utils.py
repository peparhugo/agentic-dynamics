import re
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from .extensions import db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def generate_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["JWT_EXPIRATION_SECONDS"]),
    }
    return jwt.encode(
        payload,
        current_app.config["SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["SECRET_KEY"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = header[len("Bearer "):].strip()
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        from .models import User

        user = db.session.get(User, int(payload["sub"]))
        if user is None:
            return jsonify({"error": "User no longer exists"}), 401
        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


def is_valid_email(email):
    return bool(EMAIL_RE.match(email))
