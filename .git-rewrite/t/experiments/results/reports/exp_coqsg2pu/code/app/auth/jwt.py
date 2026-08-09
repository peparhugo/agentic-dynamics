import logging
from datetime import datetime, timezone
from functools import wraps
import jwt
from flask import request, g, current_app
from app import db
from app.models.user import User


def create_access_token(user_id):
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm=current_app.config["JWT_ALGORITHM"])


def decode_access_token(token):
    return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=[current_app.config["JWT_ALGORITHM"]])


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"error": "Missing or invalid Authorization header"}, 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_access_token(token)
            user = db.session.get(User, payload["sub"])
            if user is None or not user.is_active:
                return {"error": "Invalid or inactive user"}, 401
            g.current_user = user
        except jwt.ExpiredSignatureError:
            return {"error": "Token has expired"}, 401
        except jwt.InvalidTokenError:
            return {"error": "Invalid token"}, 401
        return f(*args, **kwargs)
    return decorated


def setup_audit_logger(app):
    handler = logging.FileHandler(app.config["AUDIT_LOG_FILE"])
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger = logging.getLogger("audit")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
