from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy import or_

from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    errors = {}
    if not username:
        errors["username"] = "Username is required."
    if not email:
        errors["email"] = "Email is required."
    elif "@" not in email:
        errors["email"] = "Invalid email address."
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters long."

    if errors:
        return jsonify({"message": "Validation failed.", "errors": errors}), 400

    if User.query.filter(or_(User.username == username, User.email == email)).first():
        return jsonify({"message": "Username or email already exists."}), 409

    user = User(username=username, email=email)
    user.password_hash = _hash_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"message": "Username/email and password are required."}), 400

    user = User.query.filter(
        or_(User.username == identifier, User.email == identifier)
    ).first()

    if user is None or not _verify_password(password, user.password_hash):
        return jsonify({"message": "Invalid credentials."}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "user": user.to_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if user is None:
        return jsonify({"message": "User not found."}), 404
    return jsonify({"user": user.to_dict()}), 200


def _hash_password(password):
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password, password_hash):
    import bcrypt

    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except ValueError:
        return False
