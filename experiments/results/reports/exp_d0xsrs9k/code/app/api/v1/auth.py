import logging

from flask import Blueprint, g, jsonify, request, current_app

from app.middleware.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    login_required,
)
from app.middleware.rate_limit import rate_limit
from app.middleware.validation import validate_schema
from app.middleware.validation import (
    RegisterSchema,
    LoginSchema,
    RefreshSchema,
)
from app.models.user import User
from app.utils.errors import AuthError, ConflictError

logger = logging.getLogger("audit")
auth_bp = Blueprint("auth_v1", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/register", methods=["POST"])
@rate_limit(limit_str="10 per minute")
@validate_schema(RegisterSchema)
def register():
    data = request.validated_data
    try:
        user = User.create(
            email=data["email"],
            password=data["password"],
            name=data["name"],
        )
    except ValueError as e:
        raise ConflictError(str(e), "email_exists")

    logger.info(
        "User registered",
        extra={
            "audit_type": "user_register",
            "user_id": user.id,
            "email": user.email,
        },
    )

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    return jsonify({
        "user": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }), 201


@auth_bp.route("/login", methods=["POST"])
@rate_limit(limit_str="5 per minute")
@validate_schema(LoginSchema)
def login():
    data = request.validated_data
    user = User.authenticate(data["email"], data["password"])
    if not user:
        raise AuthError("Invalid email or password", "invalid_credentials")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    logger.info(
        "User logged in",
        extra={
            "audit_type": "user_login",
            "user_id": user.id,
            "email": user.email,
        },
    )

    return jsonify({
        "user": user.to_dict(),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    })


@auth_bp.route("/refresh", methods=["POST"])
@rate_limit(limit_str="5 per minute")
@validate_schema(RefreshSchema)
def refresh():
    data = request.validated_data
    try:
        payload = decode_token(data["refresh_token"])
    except AuthError as e:
        raise AuthError(str(e), e.error_type)

    if payload.get("type") != "refresh":
        raise AuthError("Invalid token type", "invalid_token_type")

    user = User.find_by_id(payload["sub"])
    if not user:
        raise AuthError("User not found", "user_not_found")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    })


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"user": g.current_user.to_dict()})
