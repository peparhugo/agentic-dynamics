from datetime import timedelta

from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from marshmallow import ValidationError

from app import db, limiter
from app.models import User
from app.validators import RegisterSchema, LoginSchema

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    schema = RegisterSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "messages": err.messages}), 422

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Conflict", "message": "Username already taken."}), 409

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Conflict", "message": "Email already registered."}), 409

    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role, "username": user.username},
        expires_delta=timedelta(seconds=900),
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
        expires_delta=timedelta(seconds=86400),
    )

    return (
        jsonify(
            {
                "message": "User registered successfully.",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_dict(),
            }
        ),
        201,
    )


@bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    schema = LoginSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation Error", "messages": err.messages}), 422

    user = User.query.filter_by(username=data["username"]).first()
    if user is None or not user.check_password(data["password"]):
        return jsonify({"error": "Unauthorized", "message": "Invalid username or password."}), 401

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role, "username": user.username},
        expires_delta=timedelta(seconds=900),
    )
    refresh_token = create_refresh_token(
        identity=str(user.id),
        expires_delta=timedelta(seconds=86400),
    )

    g.user_id = user.id
    g.username = user.username

    return (
        jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "user": user.to_dict(),
            }
        ),
        200,
    )


@bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
@limiter.limit("20 per minute")
def refresh():
    identity = get_jwt_identity()
    claims = get_jwt()
    access_token = create_access_token(
        identity=identity,
        additional_claims={
            "role": claims.get("role", "user"),
            "username": claims.get("username", ""),
        },
        expires_delta=timedelta(seconds=900),
    )
    return jsonify({"access_token": access_token}), 200
