import datetime
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from app.db import get_db


def encode_token(user_id):
    now = datetime.datetime.utcnow()
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=current_app.config["JWT_EXPIRES_MINUTES"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token):
    return jwt.decode(
        token,
        current_app.config["SECRET_KEY"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def _extract_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def token_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        db = get_db()
        user = db.execute(
            "SELECT id, username, email FROM users WHERE id = ?", (payload["sub"],)
        ).fetchone()
        if user is None:
            return jsonify({"error": "User not found"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return wrapper
