import functools
import jwt
from flask import request, g, jsonify, current_app

from app.models.user import find_user_by_id


class AuthError(Exception):
    def __init__(self, message, status_code=401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def decode_token(token):
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthError("Invalid token")


def jwt_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthError("Missing or invalid Authorization header")

        token = auth_header.split(" ", 1)[1]
        if not token:
            raise AuthError("Missing token")

        payload = decode_token(token)
        user = find_user_by_id(payload["sub"])
        if user is None:
            raise AuthError("User not found")

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def create_access_token(user_id):
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
        "type": "access",
    }
    return jwt.encode(
        payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"]
    )


def create_refresh_token(user_id):
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + current_app.config["JWT_REFRESH_TOKEN_EXPIRES"],
        "type": "refresh",
    }
    return jwt.encode(
        payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"]
    )
