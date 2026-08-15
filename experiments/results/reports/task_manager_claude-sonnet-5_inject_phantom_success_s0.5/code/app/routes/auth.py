from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User
from app.utils import is_valid_email

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400
    if not is_valid_email(email):
        return jsonify({"error": "invalid email address"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    user = User(username=username, email=email)
    user.set_password(password)

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "username or email already exists"}), 409

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": access_token}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username_or_email = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username_or_email or not password:
        return jsonify({"error": "username/email and password are required"}), 400

    user = User.query.filter(
        (User.username == username_or_email) | (User.email == username_or_email.lower())
    ).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": access_token}), 200


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify({"user": user.to_dict()}), 200
