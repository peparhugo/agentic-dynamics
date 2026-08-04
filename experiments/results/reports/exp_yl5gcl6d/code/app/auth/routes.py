"""Authentication endpoints: register, login, refresh, whoami."""
from flask import Blueprint, g, jsonify

from ..audit import audit
from ..errors import AuthError, ConflictError
from ..extensions import db
from ..models import User
from ..rate_limit import rate_limit
from ..validation import Email, String, validate_json
from .jwt_utils import (auth_required, create_access_token,
                        create_refresh_token, decode_token, _get_bearer_token)

auth_bp = Blueprint("auth", __name__)

REGISTER_SCHEMA = {
    "email": Email(max_length=255),
    "password": String(min_length=8, max_length=128, strip=False),
}
LOGIN_SCHEMA = {
    "email": Email(max_length=255),
    "password": String(strip=False),
}


@auth_bp.post("/register")
@rate_limit("RATELIMIT_AUTH_LIMIT", "RATELIMIT_AUTH_WINDOW")
def register():
    data = validate_json(REGISTER_SCHEMA)
    if User.query.filter_by(email=data["email"]).first():
        raise ConflictError("A user with this email already exists.")

    user = User(email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()  # assign user.id
    audit("user.register", resource_type="user", resource_id=user.id,
          status_code=201, user_id=user.id)
    db.session.commit()
    return jsonify({"data": user.to_dict()}), 201


@auth_bp.post("/login")
@rate_limit("RATELIMIT_AUTH_LIMIT", "RATELIMIT_AUTH_WINDOW")
def login():
    data = validate_json(LOGIN_SCHEMA)
    user = User.query.filter_by(email=data["email"]).first()
    if user is None or not user.check_password(data["password"]):
        audit("auth.login_failed", detail=f"email={data['email']}", status_code=401)
        db.session.commit()
        raise AuthError("Invalid email or password.", code="invalid_credentials")

    audit("auth.login", resource_type="user", resource_id=user.id,
          status_code=200, user_id=user.id)
    db.session.commit()
    return jsonify({
        "data": {
            "access_token": create_access_token(user),
            "refresh_token": create_refresh_token(user),
            "token_type": "Bearer",
        }
    })


@auth_bp.post("/refresh")
@rate_limit("RATELIMIT_AUTH_LIMIT", "RATELIMIT_AUTH_WINDOW")
def refresh():
    payload = decode_token(_get_bearer_token(), expected_type="refresh")
    user = User.query.get(int(payload["sub"]))
    if user is None:
        raise AuthError("User no longer exists.", code="token_invalid")

    audit("auth.refresh", resource_type="user", resource_id=user.id,
          status_code=200, user_id=user.id)
    db.session.commit()
    return jsonify({
        "data": {
            "access_token": create_access_token(user),
            "token_type": "Bearer",
        }
    })


@auth_bp.get("/me")
@auth_required
def me():
    return jsonify({"data": g.current_user.to_dict()})
