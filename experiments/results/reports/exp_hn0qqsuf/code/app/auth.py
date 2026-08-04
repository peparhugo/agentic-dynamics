import datetime
import jwt
import secrets
from functools import wraps
from flask import request, g, current_app
from app.models import RefreshToken as RefreshTokenModel, User


def generate_access_token(user_id):
    expire = datetime.datetime.utcnow() + datetime.timedelta(
        minutes=current_app.config["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"]
    )
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def generate_refresh_token(user_id):
    expire = datetime.datetime.utcnow() + datetime.timedelta(
        days=current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"]
    )
    token = secrets.token_urlsafe(64)
    payload = {"sub": user_id, "exp": expire, "type": "refresh", "jti": token}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256"), token


def decode_token(token):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
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
        if payload.get("type") != "access":
            return {"error": "Invalid token type"}, 401
        user = User.query.get(payload["sub"])
        if user is None:
            return {"error": "User not found"}, 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def optional_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        g.current_user = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                user = User.query.get(payload["sub"])
                if user:
                    g.current_user = user
        return f(*args, **kwargs)
    return decorated
