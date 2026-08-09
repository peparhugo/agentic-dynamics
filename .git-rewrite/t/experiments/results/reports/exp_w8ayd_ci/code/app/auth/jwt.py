from functools import wraps
import datetime

import jwt
from flask import request, g, current_app

from app.models.user import get_user_by_id
from app.utils.errors import AuthenticationError, ForbiddenError


def create_access_token(user_id, roles=None):
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + datetime.timedelta(
            hours=current_app.config.get("JWT_EXPIRATION_HOURS", 24)
        ),
    }
    if roles:
        payload["roles"] = roles

    secret = current_app.config["JWT_SECRET"]
    algorithm = current_app.config.get("JWT_ALGORITHM", "HS256")
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token):
    secret = current_app.config["JWT_SECRET"]
    algorithm = current_app.config.get("JWT_ALGORITHM", "HS256")
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Missing or invalid Authorization header")

        token = auth_header[7:]
        payload = decode_token(token)

        user_id = int(payload["sub"])
        user = get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")

        g.current_user = user
        g.current_user_id = user_id
        g.current_user_roles = payload.get("roles", [])
        return f(*args, **kwargs)

    return decorated


def requires_role(role):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Ensure jwt_required runs first
            if not hasattr(g, "current_user_roles"):
                raise AuthenticationError("Authentication required")

            if role not in g.current_user_roles:
                raise ForbiddenError(
                    message=f"Role '{role}' is required",
                    details={"required_role": role, "user_roles": g.current_user_roles},
                )
            return f(*args, **kwargs)

        return decorated

    return decorator


def jwt_optional(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header[7:]
                payload = decode_token(token)
                user_id = int(payload["sub"])
                user = get_user_by_id(user_id)
                if user:
                    g.current_user = user
                    g.current_user_id = user_id
                    g.current_user_roles = payload.get("roles", [])
            except Exception:
                pass
        return f(*args, **kwargs)

    return decorated
