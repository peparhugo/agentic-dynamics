from flask import Blueprint, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from sqlalchemy import or_

from .extensions import bcrypt, db
from .models import User
from .utils import error_response

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return error_response("username, email and password are required", 400)
    if len(password) < 6:
        return error_response("password must be at least 6 characters", 400)
    if User.query.filter_by(username=username).first():
        return error_response("username already taken", 409)
    if User.query.filter_by(email=email).first():
        return error_response("email already registered", 409)

    user = User(
        username=username,
        email=email,
        password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return {"access_token": token, "user": user.to_dict()}, 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""

    if not identifier or not password:
        return error_response("username/email and password are required", 400)

    user = User.query.filter(
        or_(User.username == identifier, User.email == identifier.lower())
    ).first()
    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return error_response("invalid credentials", 401)

    token = create_access_token(identity=str(user.id))
    return {"access_token": token, "user": user.to_dict()}, 200


@auth_bp.get("/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return error_response("user not found", 404)
    return {"user": user.to_dict()}, 200
