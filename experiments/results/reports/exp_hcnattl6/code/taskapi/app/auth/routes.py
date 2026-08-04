from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)
from ..models.user import (
    create_user,
    get_user_by_id,
    get_user_by_username,
    get_user_by_email,
    verify_password,
    user_to_dict,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    errors = {}
    if not username or len(username) < 3:
        errors["username"] = "Username must be at least 3 characters."
    if not email or "@" not in email:
        errors["email"] = "A valid email is required."
    if not password or len(password) < 6:
        errors["password"] = "Password must be at least 6 characters."

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    if get_user_by_username(username):
        errors["username"] = "Username already taken."

    if get_user_by_email(email):
        errors["email"] = "Email already registered."

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 409

    user_id = create_user(username, email, password)
    if user_id is None:
        return jsonify({"error": "Could not create user."}), 500

    user = get_user_by_id(user_id)
    access_token = create_access_token(identity=str(user_id))
    refresh_token = create_refresh_token(identity=str(user_id))

    return jsonify({
        "user": user_to_dict(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = data.get("username", data.get("email", "")).strip()
    password = data.get("password", "")

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required."}), 400

    user = None
    if "@" in identifier:
        user = get_user_by_email(identifier.lower())
    else:
        user = get_user_by_username(identifier)

    if not user or not verify_password(user, password):
        return jsonify({"error": "Invalid credentials."}), 401

    access_token = create_access_token(identity=str(user["id"]))
    refresh_token = create_refresh_token(identity=str(user["id"]))

    return jsonify({
        "user": user_to_dict(user),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    access_token = create_access_token(identity=user_id)
    return jsonify({"access_token": access_token}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = get_user_by_id(int(user_id))
    if not user:
        return jsonify({"error": "User not found."}), 404
    return jsonify({"user": user_to_dict(user)}), 200
