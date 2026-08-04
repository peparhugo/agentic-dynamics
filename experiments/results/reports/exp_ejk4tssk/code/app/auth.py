import time
from functools import wraps
from flask import request, g, current_app
import jwt
from .errors import APIError

# Simple in-memory rate limiting store: {key: [timestamps]}
_rate_store = {}

def create_token(identity: str):
    payload = {
        "sub": identity,
        "iat": int(time.time()),
        "exp": int(time.time()) + current_app.config.get("JWT_EXP_SECONDS", 3600),
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"])
    # PyJWT>=2 returns str
    if isinstance(token, bytes):
        token = token.decode()
    return token

def decode_token(token: str):
    try:
        payload = jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=[current_app.config["JWT_ALGORITHM"]])
        return payload
    except jwt.ExpiredSignatureError:
        raise APIError("token_expired", 401)
    except jwt.InvalidTokenError:
        raise APIError("invalid_token", 401)

def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise APIError("missing_authorization", 401)
        token = auth.split(None, 1)[1]
        payload = decode_token(token)
        g.current_user = payload.get("sub")
        return fn(*args, **kwargs)

    return wrapper

def rate_limit(key_fn, limit=None, period=None):
    """Rate limit decorator. key_fn() -> key string.
    Uses an in-memory store; suitable for single-process apps and tests.
    Defaults for limit/period are read from current_app at request time.
    """

    def decorator(fn):
        # closures for possible default override; we won't access current_app here
        lim = limit
        per = period

        @wraps(fn)
        def wrapper(*args, **kwargs):
            nonlocal lim, per
            # read defaults at call time (inside request/app context)
            if lim is None:
                lim = current_app.config.get("RATE_LIMIT", 5)
            if per is None:
                per = current_app.config.get("RATE_PERIOD", 60)

            key = key_fn()
            now = int(time.time())
            bucket = _rate_store.setdefault(key, [])
            # Drop old timestamps
            while bucket and bucket[0] <= now - per:
                bucket.pop(0)
            if len(bucket) >= lim:
                raise APIError("rate_limit_exceeded", 429)
            bucket.append(now)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
