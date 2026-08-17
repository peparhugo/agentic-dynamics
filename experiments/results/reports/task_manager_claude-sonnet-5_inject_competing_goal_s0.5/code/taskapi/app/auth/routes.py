import re

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from app.extensions import db
from app.models import User
from app.utils import error_response

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_registration(data):
    errors = {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if len(username) < 3:
        errors["username"] = "Username must be at least 3 characters long"
    if not EMAIL_RE.match(email):
        errors["email"] = "A valid email address is required"
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters long"

    return errors


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    errors = validate_registration(data)
    if errors:
        return error_response("Validation failed", 422, errors)

    username = data["username"].strip()
    email = data["email"].strip().lower()

    if User.query.filter_by(username=username).first():
        return error_response("Username already taken", 409)
    if User.query.filter_by(email=email).first():
        return error_response("Email already registered", 409)

    user = User(username=username, email=email)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    ), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username_or_email = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username_or_email or not password:
        return error_response("Username/email and password are required", 400)

    user = User.query.filter(
        (User.username == username_or_email) | (User.email == username_or_email.lower())
    ).first()

    if not user or not user.check_password(password):
        return error_response("Invalid credentials", 401)

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    ), 200


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({"access_token": access_token}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if not user:
        return error_response("User not found", 404)
    return jsonify(user.to_dict()), 200
