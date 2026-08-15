import base64
import hashlib
import hmac
import json
import time
from functools import wraps
from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash
from .db import get_db


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": str(user_id), "iat": int(time.time()), "exp": int(time.time()) + current_app.config["JWT_EXPIRATION_SECONDS"]}, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode()
    signature = hmac.new(current_app.config["SECRET_KEY"].encode(), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def get_current_user():
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        return None
    try:
        header, payload, signature = token[7:].split(".")
        expected = hmac.new(current_app.config["SECRET_KEY"].encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(signature)):
            return None
        claims = json.loads(_unb64(payload))
        if claims["exp"] < int(time.time()):
            return None
        return get_db().execute("SELECT id, username, email, created_at FROM users WHERE id = ?", (int(claims["sub"]),)).fetchone()
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return jsonify(error="Authentication required"), 401
        g.user = user
        return view(*args, **kwargs)
    return wrapped


__all__ = ["check_password_hash", "generate_password_hash", "create_token", "login_required"]
