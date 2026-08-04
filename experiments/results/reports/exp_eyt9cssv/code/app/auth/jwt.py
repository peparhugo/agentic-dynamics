import time

import jwt

from app.config import Config


def create_access_token(user_id):
    now = int(time.time())
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + Config.ACCESS_TOKEN_EXPIRY,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id):
    now = int(time.time())
    payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + Config.REFRESH_TOKEN_EXPIRY,
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
