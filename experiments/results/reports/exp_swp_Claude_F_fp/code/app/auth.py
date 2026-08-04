import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
import jwt
from flask import current_app, g, request
from .extensions import db
from .models import RefreshToken, User
from .errors import AuthError


def _now():
    return datetime.now(timezone.utc)


def create_access_token(user):
    payload = {
        "sub": str(user.id),
        "type": "access",
        "iat": _now(),
        "exp": _now() + timedelta(seconds=current_app.config["JWT_ACCESS_TTL"]),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def create_refresh_token(user):
    jti = uuid.uuid4().hex
    exp = _now() + timedelta(seconds=current_app.config["JWT_REFRESH_TTL"])
    db.session.add(RefreshToken(jti=jti, user_id=user.id, expires_at=exp.replace(tzinfo=None)))
    db.session.commit()
    payload = {"sub": str(user.id), "type": "refresh", "iat": _now(), "exp": exp, "jti": jti}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token, expected_type):
    try:
        payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise AuthError("token expired")
    except jwt.InvalidTokenError:
        raise AuthError("invalid token")
    if payload.get("type") != expected_type:
        raise AuthError("invalid token type")
    return payload


def rotate_refresh_token(token):
    payload = decode_token(token, "refresh")
    record = RefreshToken.query.filter_by(jti=payload["jti"]).first()
    if record is None or record.revoked:
        raise AuthError("refresh token revoked or unknown")
    record.revoked = True
    user = db.session.get(User, int(payload["sub"]))
    if user is None:
        raise AuthError("user not found")
    return user


def revoke_refresh_token(token):
    payload = decode_token(token, "refresh")
    record = RefreshToken.query.filter_by(jti=payload["jti"]).first()
    if record is None or record.revoked:
        raise AuthError("refresh token revoked or unknown")
    record.revoked = True
    db.session.commit()


def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise AuthError("missing or malformed Authorization header")
        payload = decode_token(header[7:], "access")
        user = db.session.get(User, int(payload["sub"]))
        if user is None:
            raise AuthError("user not found")
        g.current_user = user
        return f(*args, **kwargs)
    return wrapper
