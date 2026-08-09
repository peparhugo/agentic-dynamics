from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from app.models import db, User
from app.schemas import RegisterSchema, LoginSchema
from app.utils import hash_password, verify_password, generate_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "Request body must be JSON."}), 400

    try:
        data = RegisterSchema().load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already taken."}), 409

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered."}), 409

    user = User(
        username=data["username"],
        email=data["email"],
        password_hash=hash_password(data["password"]),
    )
    db.session.add(user)
    db.session.commit()

    token = generate_token(user.id)
    return jsonify({"message": "User registered.", "user": user.to_dict(), "token": token}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    json_data = request.get_json(silent=True)
    if not json_data:
        return jsonify({"error": "Request body must be JSON."}), 400

    try:
        data = LoginSchema().load(json_data)
    except ValidationError as err:
        return jsonify({"error": "Validation failed.", "details": err.messages}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not verify_password(user.password_hash, data["password"]):
        return jsonify({"error": "Invalid username or password."}), 401

    token = generate_token(user.id)
    return jsonify({"message": "Login successful.", "user": user.to_dict(), "token": token}), 200
