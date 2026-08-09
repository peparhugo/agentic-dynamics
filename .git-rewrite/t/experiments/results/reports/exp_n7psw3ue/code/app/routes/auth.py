from flask import Blueprint, request, jsonify

from app import db
from app.audit import log_audit
from app.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.errors import (
    AuthenticationError,
    ConflictError,
    TooManyRequestsError,
    ValidationError,
)
from app.models import User
from app.rate_limit import rate_limiter
from app.validators import LoginSchema, RefreshTokenSchema, RegisterSchema

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    schema = RegisterSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except Exception as e:
        raise ValidationError(str(e))

    existing = User.query.filter(
        (User.username == data["username"]) | (User.email == data["email"])
    ).first()
    if existing:
        raise ConflictError("Username or email already exists")

    user = User(
        username=data["username"],
        email=data["email"],
        password_hash=hash_password(data["password"]),
    )
    db.session.add(user)
    db.session.flush()
    log_audit(user.id, "CREATE", "user", user.id, ip_address=request.remote_addr)
    db.session.commit()

    return jsonify({"message": "User registered successfully", "user_id": user.id}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    client_ip = request.remote_addr or "127.0.0.1"
    if rate_limiter.is_rate_limited(f"login:{client_ip}", 5, 60):
        raise TooManyRequestsError("Too many login attempts. Try again in a minute.")

    schema = LoginSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except Exception as e:
        raise ValidationError(str(e))

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not verify_password(data["password"], user.password_hash):
        raise AuthenticationError("Invalid username or password")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    log_audit(user.id, "LOGIN", "session", ip_address=request.remote_addr)
    db.session.commit()

    return (
        jsonify(
            {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
                "expires_in": 900,
            }
        ),
        200,
    )


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    schema = RefreshTokenSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except Exception as e:
        raise ValidationError(str(e))

    payload = verify_token(data["refresh_token"], token_type="refresh")
    if not payload:
        raise AuthenticationError("Invalid or expired refresh token")

    user = db.session.get(User, payload["sub"])
    if not user:
        raise AuthenticationError("User not found")

    access_token = create_access_token(user.id)

    return (
        jsonify(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 900,
            }
        ),
        200,
    )
