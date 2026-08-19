from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


def make_token(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(hours=current_app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def token_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Authorization token is required"), 401
        try:
            payload = jwt.decode(header[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user = current_app.get_db().execute("SELECT id, username, email FROM users WHERE id = ?", (payload["sub"],)).fetchone()
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return jsonify(error="Invalid or expired token"), 401
        if user is None:
            return jsonify(error="User not found"), 401
        g.current_user = user
        return view(*args, **kwargs)

    return wrapped


def password_hash(password):
    return generate_password_hash(password)


def password_matches(password, hashed):
    return check_password_hash(hashed, password)
