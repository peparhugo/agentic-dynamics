from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    errors = {}
    if not username:
        errors["username"] = "Username is required"
    if not email:
        errors["email"] = "Email is required"
    if not password:
        errors["password"] = "Password is required"
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters"

    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 422

    if User.find_by_username(username):
        return jsonify({"error": "Username already taken"}), 409

    if User.find_by_email(email):
        return jsonify({"error": "Email already registered"}), 409

    user_id = User.create(username, email, password)
    if user_id is None:
        return jsonify({"error": "Registration failed"}), 500

    user = User.find_by_id(user_id)
    token = create_access_token(identity=str(user["id"]))
    return jsonify({"user": User.to_dict(user), "access_token": token}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 422

    user = User.authenticate(username, password)
    if not user:
        return jsonify({"error": "Invalid username or password"}), 401

    token = create_access_token(identity=str(user["id"]))
    return jsonify({"user": User.to_dict(user), "access_token": token}), 200
