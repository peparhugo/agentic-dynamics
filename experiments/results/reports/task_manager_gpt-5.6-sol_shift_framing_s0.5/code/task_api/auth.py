from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

auth_bp = Blueprint("auth", __name__)


def error(message, status):
    return jsonify(error=message), status


def token_for(user_id):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("missing bearer token", 401)
        try:
            payload = jwt.decode(
                header[7:], current_app.config["JWT_SECRET"], algorithms=["HS256"]
            )
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return error("invalid or expired token", 401)
        user = get_db().execute(
            "SELECT id, username FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user is None:
            return error("invalid or expired token", 401)
        g.user = user
        return view(*args, **kwargs)

    return wrapped


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not username.strip():
        return error("username is required", 400)
    if not isinstance(password, str) or len(password) < 8:
        return error("password must be at least 8 characters", 400)

    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username.strip(), generate_password_hash(password)),
        )
        db.commit()
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return error("username already exists", 409)
        raise
    return jsonify(id=cursor.lastrowid, username=username.strip()), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return error("username and password are required", 400)
    user = get_db().execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if user is None or not check_password_hash(user["password_hash"], password):
        return error("invalid credentials", 401)
    return jsonify(access_token=token_for(user["id"]), token_type="Bearer")
