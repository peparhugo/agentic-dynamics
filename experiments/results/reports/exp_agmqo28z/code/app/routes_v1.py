from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import select, func
from app import db
from app.models import User, AuditLog
from app.auth import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    require_auth,
)
from app.rate_limit import rate_limit_login
from app.validators import (
    validate_registration,
    validate_login,
    validate_user_update,
    validate_pagination,
)
from app.errors import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    ConflictError,
)
from app.audit import log_audit

v1 = Blueprint("v1", __name__, url_prefix="/v1")

auth = Blueprint("v1_auth", __name__, url_prefix="/v1/auth")


@auth.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if data is None:
        raise BadRequestError("Request body must be valid JSON")

    validated = validate_registration(data)

    if User.query.filter_by(username=validated["username"]).first():
        raise ConflictError("Username already exists")

    if User.query.filter_by(email=validated["email"]).first():
        raise ConflictError("Email already exists")

    user = User(
        username=validated["username"],
        email=validated["email"],
        password_hash=generate_password_hash(validated["password"]),
    )
    db.session.add(user)
    db.session.flush()

    log_audit("register", "user", user.id, {"username": user.username})
    db.session.commit()

    access_token = generate_access_token(user.id)
    refresh_token = generate_refresh_token(user.id)

    return (
        jsonify(
            {
                "user": user.to_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ),
        201,
    )


@auth.route("/login", methods=["POST"])
@rate_limit_login
def login():
    data = request.get_json(silent=True)
    if data is None:
        raise BadRequestError("Request body must be valid JSON")

    validated = validate_login(data)
    credentials = validated["username_or_email"]

    user = User.query.filter(
        (User.username == credentials) | (User.email == credentials)
    ).first()

    if user is None or not check_password_hash(user.password_hash, validated["password"]):
        raise AuthenticationError("Invalid credentials")

    log_audit("login", "user", user.id, {"username": user.username})
    db.session.commit()

    access_token = generate_access_token(user.id)
    refresh_token = generate_refresh_token(user.id)

    return jsonify(
        {
            "user": user.to_dict(),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    )


@auth.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True)
    if data is None:
        raise BadRequestError("Request body must be valid JSON")

    refresh_token_value = data.get("refresh_token")
    if not refresh_token_value:
        raise BadRequestError("refresh_token is required")

    payload = decode_token(refresh_token_value)

    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")

    user = db.session.get(User, payload["sub"])
    if user is None:
        raise AuthenticationError("User not found")

    access_token = generate_access_token(user.id)
    new_refresh_token = generate_refresh_token(user.id)

    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
        }
    )


users_bp = Blueprint("v1_users", __name__, url_prefix="/v1/users")


@users_bp.route("", methods=["GET"])
@require_auth
def list_users():
    page, per_page = validate_pagination(
        request.args.get("page", 1),
        request.args.get("per_page", 20),
    )

    pagination = User.query.order_by(User.id).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify(
        {
            "data": [u.to_dict() for u in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_prev": pagination.has_prev,
            },
        }
    )


@users_bp.route("/<int:user_id>", methods=["GET"])
@require_auth
def get_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return jsonify({"data": user.to_dict()})


@users_bp.route("/<int:user_id>", methods=["PUT"])
@require_auth
def update_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    if user.id != g.current_user_id:
        raise AuthenticationError("You can only update your own profile")

    data = request.get_json(silent=True)
    if data is None:
        raise BadRequestError("Request body must be valid JSON")

    validated = validate_user_update(data)

    if "username" in validated:
        existing = User.query.filter(
            User.username == validated["username"], User.id != user_id
        ).first()
        if existing:
            raise ConflictError("Username already taken")
        user.username = validated["username"]

    if "email" in validated:
        existing = User.query.filter(
            User.email == validated["email"], User.id != user_id
        ).first()
        if existing:
            raise ConflictError("Email already taken")
        user.email = validated["email"]

    if "password" in validated:
        user.password_hash = generate_password_hash(validated["password"])

    user.updated_at = datetime.now(timezone.utc)

    log_audit("update", "user", user.id, {"updated_fields": list(validated.keys())})
    db.session.commit()

    return jsonify({"data": user.to_dict()})


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_auth
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")

    if user.id != g.current_user_id:
        raise AuthenticationError("You can only delete your own profile")

    log_audit("delete", "user", user.id, {"username": user.username})
    db.session.delete(user)
    db.session.commit()

    return jsonify({"message": "User deleted"}), 200


def register_v1_routes(app):
    app.register_blueprint(auth)
    app.register_blueprint(users_bp)
