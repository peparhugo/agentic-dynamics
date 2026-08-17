import base64
import hashlib
import hmac
import json
import time

from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password):
    return generate_password_hash(password)


def verify_password(stored, password):
    return check_password_hash(stored, password)


def _b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id):
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": user_id, "iat": int(time.time()), "exp": int(time.time()) + current_app.config["JWT_EXPIRES_SECONDS"]}, separators=(",", ":")).encode())
    message = f"{header}.{payload}".encode()
    signature = _b64(hmac.new(current_app.config["SECRET_KEY"].encode(), message, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def auth_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        value = request.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            return jsonify(error="unauthorized", message="Bearer token required"), 401
        try:
            encoded_header, encoded_payload, encoded_signature = value[7:].split(".")
            message = f"{encoded_header}.{encoded_payload}".encode()
            expected = _b64(hmac.new(current_app.config["SECRET_KEY"].encode(), message, hashlib.sha256).digest())
            if not hmac.compare_digest(expected, encoded_signature):
                raise ValueError
            payload = json.loads(_unb64(encoded_payload))
            if payload["exp"] < time.time():
                return jsonify(error="unauthorized", message="Token expired"), 401
            g.user_id = int(payload["sub"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return jsonify(error="unauthorized", message="Invalid token"), 401
        return view(*args, **kwargs)

    return wrapped
