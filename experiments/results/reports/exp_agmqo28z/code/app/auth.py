import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, g, current_app
from app import db
from app.models import User
from app.errors import AuthenticationError


def generate_access_token(user_id):
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def generate_refresh_token(user_id):
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc)
        + timedelta(seconds=current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token):
    try:
        payload = jwt.decode(
            token, current_app.config["JWT_SECRET"], algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Missing or invalid authorization header")

        token = auth_header.split(" ", 1)[1]
        payload = decode_token(token)

        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")

        g.current_user_id = payload["sub"]
        user = db.session.get(User, g.current_user_id)
        if user is None:
            raise AuthenticationError("User not found")

        g.current_user = user
        return f(*args, **kwargs)

    return decorated
