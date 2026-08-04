from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity, current_user
from app.models import db, User
from app.utils.validators import validate_body, RegisterSchema, LoginSchema
from app.utils.errors import Conflict, Unauthorized
from app.middleware.rate_limiter import limiter

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/register", methods=["POST"])
@limiter.limit("5 per minute")
@validate_body(RegisterSchema)
def register():
    data = request.validated_data

    if User.query.filter_by(email=data["email"]).first():
        raise Conflict("Email already registered")
    if User.query.filter_by(username=data["username"]).first():
        raise Conflict("Username already taken")

    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "data": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 201


@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit("10 per minute")
@validate_body(LoginSchema)
def login():
    data = request.validated_data

    user = User.query.filter_by(email=data["email"]).first()
    if not user or not user.check_password(data["password"]):
        raise Unauthorized("Invalid email or password")

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "data": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
    })


@auth_bp.route("/api/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    return jsonify({"access_token": access_token})


@auth_bp.route("/api/me", methods=["GET"])
@jwt_required()
def me():
    return jsonify({"data": current_user.to_dict()})
