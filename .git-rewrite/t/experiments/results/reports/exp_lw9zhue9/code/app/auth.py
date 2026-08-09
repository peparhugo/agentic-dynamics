import datetime as dt
from functools import wraps
from typing import Any, Optional

import jwt
from flask import current_app, request, jsonify


def generate_jwt(user_id: str, extra: Optional[dict] = None, expires_in_seconds: int = 3600) -> str:
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": int(dt.datetime.utcnow().timestamp()),
        "exp": int((dt.datetime.utcnow() + dt.timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])  # type: ignore[arg-type]
    # PyJWT returns str in v2
    return token  # type: ignore[return-value]


def decode_jwt(token: str) -> dict:
    return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[current_app.config["JWT_ALGORITHM"]])


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "unauthorized", "message": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_jwt(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "unauthorized", "message": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "unauthorized", "message": "Invalid token"}), 401
        # Attach identity to request context for audit logging and handlers
        request.user_id = payload.get("sub")  # type: ignore[attr-defined]
        return fn(*args, **kwargs)

    return wrapper
