from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User
from app.utils import get_current_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    errors = {}
    if not username:
        errors["username"] = "Username is required."
    if not email:
        errors["email"] = "Email is required."
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters long."

    if errors:
        return jsonify({"error": "Validation failed", "fields": errors}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already taken."}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered."}), 409

    user = User(username=username, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()

    return jsonify(user.to_dict()), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required."}), 400

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

    if user is None or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid credentials."}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "user": user.to_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user = get_current_user()
    if user is None:
        return jsonify({"error": "User not found."}), 401
    return jsonify(user.to_dict()), 200
