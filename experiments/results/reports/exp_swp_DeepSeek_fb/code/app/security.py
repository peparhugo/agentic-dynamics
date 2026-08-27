import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from flask import current_app

from .errors import UnauthorizedError
from .extensions import db
from .models import RefreshToken


def _hash_token(raw):
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_access_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "type": "access",
        "jti": secrets.token_hex(16),
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=current_app.config["JWT_ACCESS_TOKEN_EXPIRES"])).timestamp()
        ),
    }
    return pyjwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def create_refresh_token(user):
    raw = secrets.token_urlsafe(48)
    record = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        expires_at=_now()
        + timedelta(seconds=current_app.config["JWT_REFRESH_TOKEN_EXPIRES"]),
    )
    db.session.add(record)
    db.session.commit()
    return raw


def decode_access_token(token):
    try:
        payload = pyjwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],
        )
    except pyjwt.ExpiredSignatureError:
        raise UnauthorizedError("Access token has expired", error_code="token_expired")
    except pyjwt.InvalidTokenError:
        raise UnauthorizedError("Invalid access token", error_code="token_invalid")

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type", error_code="token_invalid")
    return payload


def revoke_refresh_token(raw):
    record = RefreshToken.query.filter_by(token_hash=_hash_token(raw)).first()
    if record is None:
        return False
    record.revoked = True
    db.session.commit()
    return True


def resolve_refresh_token(raw):
    record = RefreshToken.query.filter_by(token_hash=_hash_token(raw)).first()
    if record is None or record.revoked:
        raise UnauthorizedError("Invalid refresh token", error_code="token_invalid")
    if record.expires_at < _now():
        raise UnauthorizedError("Refresh token has expired", error_code="token_expired")
    return record
