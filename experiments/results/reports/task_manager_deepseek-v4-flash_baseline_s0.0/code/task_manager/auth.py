import re

from flask import Blueprint, g, jsonify, request

from .extensions import db
from .models import User
from .utils import encode_access_token, token_required

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _error(message, status=400):
    return jsonify(error=message), status


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "user").strip().lower()

    if not username:
        return _error("username is required")
    if len(username) < 3 or len(username) > 80:
        return _error("username must be between 3 and 80 characters")
    if not email:
        return _error("email is required")
    if not EMAIL_RE.match(email):
        return _error("email must be a valid email address")
    if not password:
        return _error("password is required")
    if len(password) < 6:
        return _error("password must be at least 6 characters")
    if role not in ("user", "admin"):
        return _error("role must be one of: user, admin")

    if User.query.filter_by(username=username).first() is not None:
        return _error("username already taken", 409)
    if User.query.filter_by(email=email).first() is not None:
        return _error("email already registered", 409)

    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = encode_access_token(user.id)
    return jsonify(message="User registered", token=token, user=user.to_dict()), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not password or (not username and not email):
        return _error("username (or email) and password are required")

    if username:
        user = User.query.filter_by(username=username).first()
    else:
        user = User.query.filter_by(email=email).first()

    if user is None or not user.check_password(password):
        return _error("Invalid credentials", 401)

    token = encode_access_token(user.id)
    return jsonify(access_token=token, token_type="bearer", user=user.to_dict()), 200


@auth_bp.get("/me")
@token_required
def me():
    return jsonify(user=g.current_user.to_dict()), 200
