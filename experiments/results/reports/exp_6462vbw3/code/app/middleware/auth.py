import jwt
import datetime
from functools import wraps
from flask import request, g, current_app
from app.models.user import User


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(
            seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]
        ),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return {"error": "Missing or invalid Authorization header"}, 401
        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)
        if payload is None:
            return {"error": "Invalid or expired token"}, 401
        user = User.query.get(payload["sub"])
        if user is None or not user.is_active:
            return {"error": "User not found or deactivated"}, 401
        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.current_user.role != "admin":
            return {"error": "Admin privileges required"}, 403
        return f(*args, **kwargs)

    return decorated


def optional_login(f):
    """If a valid token is present, load the user; otherwise continue anonymously."""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token)
            if payload is not None:
                user = User.query.get(payload["sub"])
                if user and user.is_active:
                    g.current_user = user
                    return f(*args, **kwargs)
        g.current_user = None
        return f(*args, **kwargs)

    return decorated
