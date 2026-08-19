import re
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request

from .db import get_db
from .errors import ApiError

bp = Blueprint("auth", __name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")


def hash_password(password):
    import hashlib
    import hmac

    salt = current_app.config["SECRET_KEY"].encode("utf-8")
    return hmac.new(salt, password.encode("utf-8"), hashlib.sha256).hexdigest()


def _create_token(user_id, username):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(hours=current_app.config["JWT_EXPIRATION_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def token_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise ApiError("Missing or invalid Authorization header", 401)
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ApiError("Token has expired", 401)
        except jwt.InvalidTokenError:
            raise ApiError("Invalid token", 401)

        user_id = int(payload["sub"])
        user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise ApiError("User no longer exists", 401)

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


def _validate_credentials(payload):
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise ApiError("username and password are required", 400)
    if not USERNAME_RE.match(username):
        raise ApiError(
            "username must be 3-50 characters and only contain letters, digits, '.', '_', '-'",
            400,
        )
    if len(password) < 6:
        raise ApiError("password must be at least 6 characters", 400)
    return username, password


@bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username, password = _validate_credentials(payload)
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        raise ApiError("Username already taken", 409)
    cur = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, hash_password(password)),
    )
    db.commit()
    user_id = cur.lastrowid
    return (
        jsonify(
            {
                "id": user_id,
                "username": username,
                "token": _create_token(user_id, username),
            }
        ),
        201,
    )


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = payload.get("username")
    password = payload.get("password")
    if not username or not password:
        raise ApiError("username and password are required", 400)

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, hash_password(password)),
    ).fetchone()
    if user is None:
        raise ApiError("Invalid username or password", 401)
    return jsonify(
        {
            "id": user["id"],
            "username": user["username"],
            "token": _create_token(user["id"], user["username"]),
        }
    )


@bp.get("/me")
@token_required
def me():
    user = g.current_user
    return jsonify({"id": user["id"], "username": user["username"], "created_at": user["created_at"]})
