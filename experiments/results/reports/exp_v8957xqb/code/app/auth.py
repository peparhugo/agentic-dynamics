from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import User

auth_bp = Blueprint("auth", __name__)


def _validate_required(data, fields):
    missing = [f for f in fields if not data.get(f)]
    if missing:
        return missing
    return None


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    missing = _validate_required(data, ["username", "email", "password"])
    if missing:
        return jsonify({"error": "Validation Error", "message": f"Missing fields: {', '.join(missing)}"}), 400

    username = data["username"].strip()
    email = data["email"].strip().lower()
    password = data["password"]

    if len(password) < 6:
        return jsonify({"error": "Validation Error", "message": "Password must be at least 6 characters"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Conflict", "message": "Username already exists"}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Conflict", "message": "Email already exists"}), 409

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": access_token}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    missing = _validate_required(data, ["username", "password"])
    if missing:
        return jsonify({"error": "Validation Error", "message": f"Missing fields: {', '.join(missing)}"}), 400

    username = data["username"].strip()
    password = data["password"]

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Unauthorized", "message": "Invalid username or password"}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": access_token}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Not Found", "message": "User not found"}), 404
    return jsonify(user.to_dict()), 200
