import jwt
from flask import current_app


def create_access_token(user_id: str, role: str) -> str:
    app = current_app._get_current_object()
    payload = {"sub": user_id, "role": role, "type": "access"}
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])


def create_refresh_token(user_id: str, role: str) -> str:
    app = current_app._get_current_object()
    payload = {"sub": user_id, "role": role, "type": "refresh"}
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm=app.config["JWT_ALGORITHM"])


def decode_token(token: str) -> dict:
    app = current_app._get_current_object()
    return jwt.decode(token, app.config["SECRET_KEY"], algorithms=[app.config["JWT_ALGORITHM"]])
