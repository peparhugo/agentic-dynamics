from flask import Blueprint, g, jsonify, request
from sqlalchemy import or_

from .extensions import db
from .models import User
from .utils import generate_token, is_valid_email, login_required

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

MIN_PASSWORD_LENGTH = 8


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    errors = {}
    if not username:
        errors["username"] = "Username is required."
    elif len(username) > 80:
        errors["username"] = "Username must be 80 characters or fewer."

    if not email:
        errors["email"] = "Email is required."
    elif not is_valid_email(email):
        errors["email"] = "Email is not valid."

    if not password:
        errors["password"] = "Password is required."
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors["password"] = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists."}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({"user": user.to_dict(), "token": token}), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required."}), 400

    user = User.query.filter(
        or_(User.username == identifier, User.email == identifier.lower())
    ).first()

    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid credentials."}), 401

    token = generate_token(user.id)
    return jsonify({"user": user.to_dict(), "token": token}), 200


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": g.current_user.to_dict()}), 200
