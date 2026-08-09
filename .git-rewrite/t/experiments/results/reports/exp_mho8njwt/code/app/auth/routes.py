import hashlib
import secrets
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from marshmallow import ValidationError

from app.extensions import db, jwt, limiter
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.schemas.auth import LoginSchema, RefreshSchema
from app.utils.audit import log_audit

auth_bp = Blueprint("auth", __name__)


@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    token_type = jwt_payload.get("type")
    if token_type == "refresh":
        token = RefreshToken.query.filter_by(jti=jti, revoked=True).first()
        return token is not None
    return False


@auth_bp.route("/register", methods=["POST"])
def register():
    schema = LoginSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 422

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already exists"}), 409

    user = User(username=data["username"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    log_audit("register", "user", user.id, {"username": user.username}, user_id=user.id)

    return jsonify({"message": "User registered successfully", "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
@limiter.limit(current_app.config.get("LOGIN_RATE_LIMIT", "5 per minute"))
def login():
    schema = LoginSchema()
    try:
        data = schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"error": "Validation failed", "details": err.messages}), 422

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        log_audit("login_failed", "user", None, {"username": data["username"]})
        return jsonify({"error": "Invalid username or password"}), 401

    access_token = create_access_token(
        identity=str(user.id), additional_claims={"username": user.username}
    )
    refresh_token_str = create_refresh_token(
        identity=str(user.id), additional_claims={"username": user.username}
    )

    from flask_jwt_extended import decode_token

    decoded_refresh = decode_token(refresh_token_str)
    jti = decoded_refresh["jti"]
    exp_timestamp = decoded_refresh["exp"]
    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

    token_hash = hashlib.sha256(refresh_token_str.encode()).hexdigest()

    refresh_record = RefreshToken(
        jti=jti,
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.session.add(refresh_record)
    db.session.commit()

    log_audit("login", "user", user.id, {"username": user.username}, user_id=user.id)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "Bearer",
    }), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    jti = get_jwt()["jti"]
    token_record = RefreshToken.query.filter_by(jti=jti).first()

    if token_record and token_record.revoked:
        return jsonify({"error": "Refresh token has been revoked"}), 401

    current_user_id = get_jwt_identity()
    claims = get_jwt()
    username = claims.get("username", "")

    new_access_token = create_access_token(
        identity=current_user_id, additional_claims={"username": username}
    )
    new_refresh_token = create_refresh_token(
        identity=current_user_id, additional_claims={"username": username}
    )

    from flask_jwt_extended import decode_token

    decoded_new = decode_token(new_refresh_token)
    new_jti = decoded_new["jti"]
    new_exp = decoded_new["exp"]
    new_expires_at = datetime.fromtimestamp(new_exp, tz=timezone.utc)

    new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()

    if token_record:
        token_record.revoked = True

    new_record = RefreshToken(
        jti=new_jti,
        user_id=int(current_user_id),
        token_hash=new_token_hash,
        expires_at=new_expires_at,
    )
    db.session.add(new_record)
    db.session.commit()

    log_audit("token_refresh", "user", int(current_user_id), user_id=int(current_user_id))

    return jsonify({
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "Bearer",
    }), 200


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    user_id = get_jwt_identity()

    if "refresh" in request.get_json(silent=True) or {}:
        return jsonify({"error": "Include refresh_token in body to revoke it"}), 422

    RefreshToken.query.filter_by(user_id=user_id).update({"revoked": True})
    db.session.commit()

    log_audit("logout", "user", int(user_id), user_id=int(user_id))
    return jsonify({"message": "Logged out successfully"}), 200
