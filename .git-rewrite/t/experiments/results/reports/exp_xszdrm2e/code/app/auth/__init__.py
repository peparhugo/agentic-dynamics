from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    verify_jwt_in_request,
)
from functools import wraps


jwt = JWTManager()


def init_auth(app):
    jwt.init_app(app)


def generate_tokens(user_id, additional_claims=None):
    access_token = create_access_token(
        identity=user_id, additional_claims=additional_claims or {}
    )
    refresh_token = create_refresh_token(
        identity=user_id, additional_claims=additional_claims or {}
    )
    return {"access_token": access_token, "refresh_token": refresh_token}


def refresh_access_token():
    identity = get_jwt_identity()
    return create_access_token(identity=identity)


def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        return fn(*args, **kwargs)

    return wrapper


def require_role(role):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt_identity()
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def get_current_user_id():
    verify_jwt_in_request()
    return get_jwt_identity()
