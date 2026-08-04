from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.auth import check_rate_limit, decode_token, generate_token, login_required
from app.errors import APIError
from app.middleware import log_audit
from app.models import User
from app.validators import (
    LoginSchema,
    RefreshSchema,
    RegisterSchema,
    validate_request,
)

from . import bp


@bp.route("/auth/register", methods=["POST"])
def register():
    data = validate_request(RegisterSchema(), request.get_json(silent=True) or {})

    if User.query.filter_by(username=data["username"]).first():
        raise APIError("Username already taken", 409)

    if User.query.filter_by(email=data["email"]).first():
        raise APIError("Email already registered", 409)

    user = User(
        username=data["username"],
        email=data["email"],
        password_hash=generate_password_hash(data["password"]),
    )
    db.session.add(user)
    db.session.commit()

    log_audit(
        user_id=user.id,
        action="register",
        resource="user",
        resource_id=user.id,
        request=request,
    )

    return jsonify(user.to_dict()), 201


@bp.route("/auth/login", methods=["POST"])
def login():
    ip = request.remote_addr or "127.0.0.1"
    limit = current_app.config["RATE_LIMIT_LOGIN"]
    check_rate_limit(f"login:{ip}", limit[0], limit[1])

    data = validate_request(LoginSchema(), request.get_json(silent=True) or {})

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not check_password_hash(user.password_hash, data["password"]):
        raise APIError("Invalid username or password", 401)

    access_token = generate_token(user.id, "access")
    refresh_token = generate_token(user.id, "refresh")

    return jsonify({"access_token": access_token, "refresh_token": refresh_token}), 200


@bp.route("/auth/refresh", methods=["POST"])
def refresh():
    data = validate_request(RefreshSchema(), request.get_json(silent=True) or {})

    payload = decode_token(data["refresh_token"], token_type="refresh")
    user = User.query.get(payload["sub"])
    if not user:
        raise APIError("User not found", 401)

    access_token = generate_token(user.id, "access")
    return jsonify({"access_token": access_token}), 200


@bp.route("/auth/me", methods=["GET"])
@login_required
def me():
    return jsonify(g.current_user.to_dict()), 200
