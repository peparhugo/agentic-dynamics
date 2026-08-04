from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


jwt = JWTManager()


def _key_func():
    # Prefer JWT subject for per-user limiting; fallback to remote addr
    try:
        from flask_jwt_extended import get_jwt

        claims = get_jwt()
        if claims and "sub" in claims:
            return f"user:{claims['sub']}"
    except Exception:
        pass
    return get_remote_address()


limiter = Limiter(key_func=_key_func, default_limits=["100 per minute"])  # default replaced by app config when init_app
