import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from functools import wraps

from flask import current_app, g, jsonify, request

from .db import get_db


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000)
    return base64.b64encode(salt + digest).decode()


def verify_password(password, stored):
    raw = base64.b64decode(stored.encode())
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), raw[:16], 310000)
    return hmac.compare_digest(candidate, raw[16:])


def _encode_part(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode_part(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    header = _encode_part(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode_part(json.dumps({"sub": user_id, "exp": int(time.time()) + current_app.config["JWT_EXPIRATION_SECONDS"]}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _encode_part(hmac.new(current_app.config["SECRET_KEY"].encode(), signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_token(token):
    try:
        header, payload, signature = token.split(".")
        expected = _encode_part(hmac.new(current_app.config["SECRET_KEY"].encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_decode_part(payload))
        if not isinstance(claims.get("sub"), int) or claims.get("exp", 0) < time.time():
            return None
        return claims
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error):
        return None


def auth_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        parts = request.headers.get("Authorization", "").split()
        claims = decode_token(parts[1]) if len(parts) == 2 and parts[0].lower() == "bearer" else None
        if claims is None:
            return jsonify(error="authentication required"), 401
        user = get_db().execute("SELECT id, email, name FROM users WHERE id = ?", (claims["sub"],)).fetchone()
        if user is None:
            return jsonify(error="authentication required"), 401
        g.current_user = user
        return view(*args, **kwargs)
    return wrapped
