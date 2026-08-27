from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt_identity,
    jwt_required,
)

from .audit import log_action
from .errors import (
    ConflictError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)
from .extensions import db
from .models import User
from .validation import (
    get_json_body,
    raise_for_errors,
    validate_login,
    validate_register,
)

auth_bp = Blueprint("auth", __name__)


def _tokens_response(user):
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
    }


@auth_bp.route("/auth/register", methods=["POST"])
def register():
    data = get_json_body()
    errors = validate_register(data)
    raise_for_errors(errors)

    email = data["email"].strip().lower()
    password = data["password"]

    if User.query.filter_by(email=email).first() is not None:
        raise ConflictError("A user with that email already exists.")

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    log_action("create", "user", resource_id=user.id, user_id=user.id)

    return jsonify({"user": user.to_dict(), **_tokens_response(user)}), 201


@auth_bp.route("/auth/login", methods=["POST"])
def login():
    limiter = getattr(current_app, "login_limiter", None)
    client_ip = request.headers.get(
        "X-Forwarded-For", request.remote_addr or ""
    ).split(",")[0].strip()

    if limiter is not None and current_app.config.get("RATE_LIMIT_ENABLED", True):
        allowed, retry_after = limiter.allow(client_ip)
        if not allowed:
            raise RateLimitError(
                "Too many login attempts. Please try again later.",
                retry_after=retry_after,
            )

    data = get_json_body()
    errors = validate_login(data)
    raise_for_errors(errors)

    email = data["email"].strip().lower()
    password = data["password"]

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        raise UnauthorizedError("Invalid email or password.")

    log_action("login", "user", resource_id=user.id, user_id=user.id)

    return jsonify({"user": user.to_dict(), **_tokens_response(user)}), 200


@auth_bp.route("/auth/refresh", methods=["POST"])
def refresh():
    data = get_json_body() or {}
    token = None
    if isinstance(data, dict) and data.get("refresh_token"):
        token = data["refresh_token"]
    else:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if not token:
        raise ValidationError(
            "A refresh token is required.", fields={"refresh_token": "Required."}
        )

    try:
        claims = decode_token(token)
    except Exception:
        raise UnauthorizedError("Invalid or expired refresh token.")

    if claims.get("type") != "refresh":
        raise UnauthorizedError("Token is not a valid refresh token.")

    identity = claims.get("sub")
    user = db.session.get(User, int(identity)) if identity is not None else None
    if user is None:
        raise UnauthorizedError("User no longer exists.")

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": current_app.config["JWT_ACCESS_TOKEN_EXPIRES"],
        }
    ), 200


@auth_bp.route("/auth/me", methods=["GET"])
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    return jsonify({"user": user.to_dict()}), 200
