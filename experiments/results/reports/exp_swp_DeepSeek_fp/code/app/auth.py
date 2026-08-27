import jwt
from flask import Blueprint, current_app, jsonify

from .audit import log_audit
from .errors import APIError
from .extensions import db
from .models import User
from .rate_limit import get_client_ip
from .tokens import create_access_token, create_refresh_token, decode_token
from .validators import get_json, require_email, require_string

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = get_json()
    username = require_string(data, "username", min_length=3, max_length=80)
    email = require_email(data, "email")
    password = require_string(data, "password", min_length=8, max_length=128)

    if User.query.filter_by(username=username).first() is not None:
        raise APIError("Username already taken", 409, "username_taken")
    if User.query.filter_by(email=email).first() is not None:
        raise APIError("Email already registered", 409, "email_taken")

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    log_audit("register", "user", resource_id=user.id, user_id=user.id)
    db.session.commit()

    return jsonify(user.to_dict()), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    limiter = current_app.rate_limiter
    ip = get_client_ip()

    if limiter.is_limited(ip):
        resp = jsonify({"error": "Too many login attempts. Try again later.", "code": "rate_limited"})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(limiter.retry_after(ip))
        return resp

    limiter.hit(ip)

    data = get_json()
    identifier = require_string(data, "username", required=False) or None
    email = require_email(data, "email", required=False)
    password = require_string(data, "password")

    if not identifier and not email:
        raise APIError("Either 'username' or 'email' is required", 400, "missing_identifier")

    user = None
    if identifier:
        user = User.query.filter_by(username=identifier).first()
    elif email:
        user = User.query.filter_by(email=email).first()

    if user is None or not user.check_password(password):
        raise APIError("Invalid credentials", 401, "invalid_credentials")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return jsonify(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": current_app.config["ACCESS_TOKEN_EXPIRE_MINUTES"] * 60,
        }
    ), 200


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = get_json()
    refresh_token = require_string(data, "refresh_token")

    try:
        payload = decode_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise APIError("Refresh token has expired", 401, "token_expired")
    except jwt.InvalidTokenError:
        raise APIError("Invalid refresh token", 401, "invalid_token")

    if payload.get("type") != "refresh":
        raise APIError("Invalid token type", 401, "invalid_token_type")

    sub = payload.get("sub")
    if sub is None:
        raise APIError("Invalid refresh token", 401, "invalid_token")

    user = db.session.get(User, int(sub))
    if user is None:
        raise APIError("User no longer exists", 401, "user_not_found")

    access_token = create_access_token(user.id)
    return jsonify(
        {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": current_app.config["ACCESS_TOKEN_EXPIRE_MINUTES"] * 60,
        }
    ), 200
