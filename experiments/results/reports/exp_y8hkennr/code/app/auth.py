from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)


def token_for(user):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user["id"]), "iat": now, "exp": now + timedelta(seconds=current_app.config["JWT_TTL_SECONDS"])}, current_app.config["SECRET_KEY"], algorithm="HS256")


def current_user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Authorization bearer token required"), 401
        try:
            payload = jwt.decode(header[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user = get_db().execute("SELECT id, email, name, created_at FROM users WHERE id = ?", (payload["sub"],)).fetchone()
        except (jwt.InvalidTokenError, KeyError, ValueError):
            user = None
        if user is None:
            return jsonify(error="Invalid or expired token"), 401
        g.user = user
        return view(*args, **kwargs)
    return wrapped


def user_json(user):
    return {"id": user["id"], "email": user["email"], "name": user["name"], "created_at": user["created_at"]}


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email, password, name = data.get("email"), data.get("password"), data.get("name")
    if not isinstance(email, str) or not isinstance(password, str) or not isinstance(name, str) or not email.strip() or len(password) < 8 or not name.strip():
        return jsonify(error="email, name, and a password of at least 8 characters are required"), 400
    db = get_db()
    try:
        cursor = db.execute("INSERT INTO users(email, password_hash, name) VALUES (?, ?, ?)", (email.strip().lower(), generate_password_hash(password), name.strip()))
        db.commit()
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            return jsonify(error="email is already registered"), 409
        raise
    user = db.execute("SELECT id, email, name, created_at FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(user=user_json(user), token=token_for(user)), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = get_db().execute("SELECT * FROM users WHERE email = ?", (str(data.get("email", "")).strip().lower(),)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], str(data.get("password", ""))):
        return jsonify(error="invalid email or password"), 401
    return jsonify(user=user_json(user), token=token_for(user))


@bp.get("/me")
@current_user_required
def me():
    return jsonify(user=user_json(g.user))
