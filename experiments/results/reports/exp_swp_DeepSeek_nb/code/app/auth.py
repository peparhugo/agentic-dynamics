from flask import Blueprint, current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .audit import log_action
from .auth_utils import (
    _decode_token,
    create_access_token,
    create_refresh_token,
    get_bearer_token,
    load_current_user,
)
from .errors import AuthenticationError, ConflictError, RateLimitError
from .extensions import db
from .models import RefreshToken, User, utcnow
from .validation import (
    validate_email,
    validate_password,
    validate_username,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/v1/auth")


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        from .errors import ValidationError

        raise ValidationError("Request body must be a JSON object")

    username = validate_username(data.get("username"))
    email = validate_email(data.get("email"))
    password = validate_password(data.get("password"))

    if User.query.filter_by(username=username).first():
        raise ConflictError("Username already exists")
    if User.query.filter_by(email=email).first():
        raise ConflictError("Email already registered")

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    db.session.flush()
    log_action(user.id, "register", "user", user.id, {"username": username})
    db.session.commit()

    return jsonify(user.to_dict()), 201


@auth_bp.post("/login")
def login():
    limiter = current_app.extensions["rate_limiter"]
    ip = request.remote_addr or "unknown"
    if not limiter.is_allowed(ip):
        retry_after = current_app.config["LOGIN_RATE_LIMIT_WINDOW"]
        raise RateLimitError(
            "Too many login attempts. Try again later.",
            details={"retry_after": retry_after},
        )

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AuthenticationError("Invalid credentials")

    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        raise AuthenticationError("Invalid credentials")

    user = User.query.filter_by(username=username).first()
    if user is None or not check_password_hash(user.password_hash, password):
        raise AuthenticationError("Invalid credentials")

    if not user.is_active:
        raise AuthenticationError("Account disabled")

    record, refresh_token = create_refresh_token(user.id)
    db.session.add(record)
    db.session.commit()

    log_action(user.id, "login", "user", user.id)
    return jsonify(
        {
            "access_token": create_access_token(user.id),
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": current_app.config["ACCESS_TOKEN_EXPIRES"],
        }
    ), 200


@auth_bp.post("/refresh")
def refresh():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AuthenticationError("Missing refresh token")
    token = data.get("refresh_token")
    if not token:
        raise AuthenticationError("Missing refresh token")

    payload = _decode_token(token, expected_type="refresh")
    jti = payload.get("jti")
    if not jti:
        raise AuthenticationError("Invalid refresh token")

    record = RefreshToken.query.filter_by(jti=jti).first()
    if record is None or not record.is_valid:
        raise AuthenticationError("Refresh token is revoked or expired")

    user = db.session.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid refresh token")

    # Rotate: revoke old refresh token, issue a new one.
    record.revoked = True
    new_record, new_refresh_token = create_refresh_token(user.id)
    db.session.add(new_record)
    db.session.commit()

    return jsonify(
        {
            "access_token": create_access_token(user.id),
            "refresh_token": new_refresh_token,
            "token_type": "Bearer",
            "expires_in": current_app.config["ACCESS_TOKEN_EXPIRES"],
        }
    ), 200


@auth_bp.post("/logout")
def logout():
    data = request.get_json(silent=True) or {}
    token = data.get("refresh_token")
    user_id = None
    try:
        load_current_user()
        user_id = g.current_user.id
    except AuthenticationError:
        pass

    if token:
        try:
            payload = _decode_token(token, expected_type="refresh")
            record = RefreshToken.query.filter_by(jti=payload.get("jti")).first()
            if record and not record.revoked:
                record.revoked = True
        except AuthenticationError:
            pass

    if user_id is not None:
        log_action(user_id, "logout", "user", user_id)
    db.session.commit()
    return jsonify({"message": "Logged out"}), 200
