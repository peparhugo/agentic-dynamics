from functools import wraps

from flask import g, jsonify, request

from app.auth.jwt import decode_token
from app.models import User


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "missing or invalid authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
        except Exception:
            return jsonify({"error": "invalid or expired token"}), 401

        if payload.get("type") != "access":
            return jsonify({"error": "invalid token type"}), 401

        user = User.query.get(payload["sub"])
        if user is None:
            return jsonify({"error": "user not found"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated
