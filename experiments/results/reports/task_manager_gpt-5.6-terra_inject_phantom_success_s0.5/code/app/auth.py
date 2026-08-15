from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .database import get_db

auth_bp = Blueprint("auth", __name__)


def error(message, status=400):
    return jsonify({"error": message}), status


def token_for(user_id):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(seconds=current_app.config["JWT_EXPIRATION_SECONDS"])},
        current_app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("missing bearer token", 401)
        try:
            payload = jwt.decode(header[7:], current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
            g.current_user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, KeyError, ValueError):
            return error("invalid or expired token", 401)
        return view(*args, **kwargs)

    return wrapped


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    name = data.get("name", "").strip()
    if not email or "@" not in email or len(password) < 8:
        return error("email and a password of at least 8 characters are required")
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (email, generate_password_hash(password), name or None),
        )
        db.commit()
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            return error("email is already registered", 409)
        raise
    return jsonify({"user": {"id": cursor.lastrowid, "email": email, "name": name or None}, "token": token_for(cursor.lastrowid)}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (data.get("email", "").strip().lower(),)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], data.get("password", "")):
        return error("invalid email or password", 401)
    return jsonify({"user": {"id": user["id"], "email": user["email"], "name": user["name"]}, "token": token_for(user["id"])})
