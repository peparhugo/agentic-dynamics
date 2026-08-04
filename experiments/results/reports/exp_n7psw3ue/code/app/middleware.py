from functools import wraps

from flask import g, request

from app.auth import verify_token
from app.errors import AuthenticationError


def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

        if not token:
            raise AuthenticationError("Missing authorization token")

        payload = verify_token(token, token_type="access")
        if not payload:
            raise AuthenticationError("Invalid or expired token")

        g.current_user_id = payload["sub"]
        return f(*args, **kwargs)

    return decorated
