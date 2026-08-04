from flask import Blueprint, jsonify, request

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.extensions import db
from app.middleware.ratelimit import login_rate_limit
from app.models import AuditLog, User
from app.validators import (
    LoginSchema,
    RefreshSchema,
    RegisterSchema,
    validate_schema,
)

bp = Blueprint("auth", __name__, url_prefix="/v1/auth")


@bp.route("/register", methods=["POST"])
@validate_schema(RegisterSchema)
def register(validated_data):
    username = validated_data["username"]
    email = validated_data["email"]
    password = validated_data["password"]

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "email already registered"}), 409

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "username already taken"}), 409

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    AuditLog.log(
        user_id=user.id,
        action="register",
        resource="user",
        resource_id=user.id,
        ip_address=request.remote_addr,
    )

    return jsonify({
        "user": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 201


@bp.route("/login", methods=["POST"])
@login_rate_limit
@validate_schema(LoginSchema)
def login(validated_data):
    email = validated_data["email"]
    password = validated_data["password"]

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid email or password"}), 401

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return jsonify({
        "user": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
    }), 200


@bp.route("/refresh", methods=["POST"])
@validate_schema(RefreshSchema)
def refresh(validated_data):
    refresh_token = validated_data["refresh_token"]

    try:
        payload = decode_token(refresh_token)
    except Exception:
        return jsonify({"error": "invalid or expired refresh token"}), 401

    if payload.get("type") != "refresh":
        return jsonify({"error": "invalid token type"}), 401

    user = User.query.get(payload["sub"])
    if user is None:
        return jsonify({"error": "user not found"}), 401

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)

    return jsonify({
        "access_token": new_access,
        "refresh_token": new_refresh,
    }), 200
