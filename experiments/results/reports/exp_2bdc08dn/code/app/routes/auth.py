from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from ..extensions import db
from ..models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/api")


def _validate_registration(data):
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    errors = []
    if not username:
        errors.append("username is required")
    if not email or "@" not in email:
        errors.append("a valid email is required")
    if len(password) < 6:
        errors.append("password must be at least 6 characters")
    return username, email, password, errors


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username, email, password, errors = _validate_registration(data)
    if errors:
        return jsonify({"errors": errors}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "username already taken"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": token}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    identifier = (
        data.get("identifier") or data.get("username") or data.get("email") or ""
    ).strip()
    password = data.get("password") or ""

    user = None
    if identifier:
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid credentials"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"user": user.to_dict(), "access_token": token})


@auth_bp.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    return jsonify({"user": user.to_dict()})
