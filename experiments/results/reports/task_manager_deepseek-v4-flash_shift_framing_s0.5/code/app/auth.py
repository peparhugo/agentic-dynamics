from functools import wraps
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app, g, jsonify, request

from app.db import get_db, row_to_dict


def issue_token(user_id):
    payload = {
        "sub": str(user_id),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(seconds=current_app.config["JWT_EXPIRATION_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _load_user_from_request():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    token = header[len("Bearer "):].strip()
    if not token:
        return None
    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        return None
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        return None
    return row_to_dict(get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        g.user = _load_user_from_request()
        if g.user is None:
            return jsonify({"error": "authentication required"}), 401
        return f(*args, **kwargs)

    return wrapper
