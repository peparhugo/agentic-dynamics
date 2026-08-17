from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    jwt_required,
)

from app.extensions import bcrypt, db
from app.models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _validate_registration(data):
    errors = []
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username:
        errors.append("username is required")
    elif len(username) < 3:
        errors.append("username must be at least 3 characters")

    if not email:
        errors.append("email is required")
    elif "@" not in email:
        errors.append("email is invalid")

    if not password:
        errors.append("password is required")
    elif len(password) < 6:
        errors.append("password must be at least 6 characters")

    return username, email, password, errors


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username, email, password, errors = _validate_registration(data)

    if errors:
        return jsonify({"message": "Validation failed", "errors": errors}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "email already exists"}), 409

    user = User(
        username=username,
        email=email,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({"id": user.id, "username": user.username, "email": user.email}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"message": "username and password are required"}), 400

    user = User.query.filter_by(username=username).first()
    if user is None or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"message": "invalid username or password"}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify(
        {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {"id": user.id, "username": user.username, "email": user.email},
        }
    ), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"message": "user not found"}), 404
    return jsonify(
        {"id": user.id, "username": user.username, "email": user.email}
    ), 200
