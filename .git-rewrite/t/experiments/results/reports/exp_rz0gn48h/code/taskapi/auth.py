import datetime
import functools

import bcrypt
import jwt
from flask import request, jsonify, g, current_app

from taskapi.database import query_one


def hash_password(password: str) -> str:
    rounds = current_app.config.get("BCRYPT_ROUNDS", 12)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode(
        "utf-8"
    )


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=current_app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(
        payload,
        current_app.config["JWT_SECRET"],
        algorithm=current_app.config["JWT_ALGORITHM"],
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

        if not token:
            return jsonify({"error": "Authentication required"}), 401

        try:
            payload = decode_token(token)
            user_id = payload["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        user = query_one("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
        if user is None:
            return jsonify({"error": "User not found"}), 401

        g.current_user = dict(user)
        return f(*args, **kwargs)

    return decorated


def optional_login(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        g.current_user = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                payload = decode_token(auth_header[7:])
                user = query_one(
                    "SELECT id, username, email FROM users WHERE id = ?",
                    (payload["sub"],),
                )
                if user:
                    g.current_user = dict(user)
            except (jwt.InvalidTokenError, jwt.ExpiredSignatureError):
                pass
        return f(*args, **kwargs)

    return decorated
