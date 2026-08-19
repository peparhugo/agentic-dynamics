from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.utils import generate_token, token_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    errors = {}
    if not username:
        errors["username"] = "Username is required"
    elif len(username) < 3:
        errors["username"] = "Username must be at least 3 characters"
    if not email:
        errors["email"] = "Email is required"
    elif "@" not in email:
        errors["email"] = "Invalid email address"
    if not password:
        errors["password"] = "Password is required"
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters"

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({"error": "Username or email already exists"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Username or email already exists"}), 409

    token = generate_token(user)
    return jsonify({"message": "User registered", "token": token, "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not identifier or not password:
        return jsonify({"error": "Username/email and password are required"}), 400

    user = User.query.filter(
        (User.username == identifier) | (User.email == identifier)
    ).first()

    if user is None or not user.check_password(password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(user)
    return jsonify({"message": "Login successful", "token": token, "user": user.to_dict()}), 200


@auth_bp.route("/me", methods=["GET"])
@token_required
def me():
    return jsonify({"user": request.current_user.to_dict()}), 200
