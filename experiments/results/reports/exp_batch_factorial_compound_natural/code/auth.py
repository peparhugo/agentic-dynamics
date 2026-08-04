import os
from functools import wraps

import jwt
from flask import request, g, jsonify

SECRET_KEY = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")


def generate_token(user_id):
    payload = {"user_id": user_id}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("user_id")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        if not token:
            return jsonify({"error": "Authorization token required"}), 401

        user_id = verify_token(token)
        if user_id is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        from models import User

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated
