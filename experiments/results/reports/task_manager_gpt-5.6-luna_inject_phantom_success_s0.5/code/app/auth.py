from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, now_iso

auth_bp = Blueprint("auth", __name__)


def issue_token(user_id):
    expiry = datetime.now(timezone.utc) + timedelta(minutes=current_app.config["JWT_EXPIRES_MINUTES"])
    return jwt.encode({"sub": str(user_id), "exp": expiry}, current_app.config["SECRET_KEY"], algorithm="HS256")


def auth_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="missing bearer token"), 401
        try:
            payload = jwt.decode(header[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"])
            user = db().execute("SELECT id, email, name, created_at FROM users WHERE id = ?", (int(payload["sub"]),)).fetchone()
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            user = None
        if user is None:
            return jsonify(error="invalid or expired token"), 401
        g.user = user
        return function(*args, **kwargs)
    return wrapped


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email, password, name = data.get("email"), data.get("password"), data.get("name")
    if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or len(password) < 8:
        return jsonify(error="email and a password of at least 8 characters are required"), 400
    if not isinstance(name, str) or not name.strip():
        return jsonify(error="name is required"), 400
    connection = db()
    try:
        cursor = connection.execute("INSERT INTO users(email, password_hash, name, created_at) VALUES (?, ?, ?, ?)",
                                    (email.strip().lower(), generate_password_hash(password), name.strip(), now_iso()))
        connection.commit()
    except Exception as error:
        if "UNIQUE" in str(error).upper():
            return jsonify(error="email is already registered"), 409
        raise
    user = {"id": cursor.lastrowid, "email": email.strip().lower(), "name": name.strip()}
    return jsonify(user=user, token=issue_token(user["id"])), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    user = db().execute("SELECT * FROM users WHERE email = ?", (str(data.get("email", "")).strip().lower(),)).fetchone()
    if user is None or not check_password_hash(user["password_hash"], str(data.get("password", ""))):
        return jsonify(error="invalid email or password"), 401
    return jsonify(user={"id": user["id"], "email": user["email"], "name": user["name"]}, token=issue_token(user["id"]))


@auth_bp.get("/me")
@auth_required
def me():
    return jsonify(user=dict(g.user))
