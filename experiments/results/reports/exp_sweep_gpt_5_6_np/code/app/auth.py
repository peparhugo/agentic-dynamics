from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import AuditLog, User
from .rate_limit import login_limiter
from .validation import json_body, validate_credentials, validate_registration


auth_bp = Blueprint("auth", __name__, url_prefix="/v1/auth")


def token_response(user):
    identity = str(user.id)
    return {
        "access_token": create_access_token(identity=identity),
        "refresh_token": create_refresh_token(identity=identity),
        "token_type": "Bearer",
    }


@auth_bp.post("/register")
def register():
    email, password = validate_registration(json_body())
    if db.session.scalar(db.select(User).where(User.email == email)):
        return jsonify(error={"code": "conflict", "message": "Email is already registered"}), 409

    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.flush()
        db.session.add(
            AuditLog(
                user_id=user.id,
                action="create",
                resource_type="user",
                resource_id=str(user.id),
                ip_address=request.remote_addr or "unknown",
                details={"email": user.email},
            )
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error={"code": "conflict", "message": "Email is already registered"}), 409
    return jsonify(user=user.to_dict(), **token_response(user)), 201


@auth_bp.post("/login")
@login_limiter.limit(maximum=5, window=60)
def login():
    email, password = validate_credentials(json_body())
    user = db.session.scalar(db.select(User).where(User.email == email))
    if user is None or not user.check_password(password):
        return jsonify(error={"code": "invalid_credentials", "message": "Invalid credentials"}), 401
    return jsonify(user=user.to_dict(), **token_response(user))


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        return jsonify(error={"code": "unauthorized", "message": "User no longer exists"}), 401
    return jsonify(access_token=create_access_token(identity=str(user.id)), token_type="Bearer")


@auth_bp.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        return jsonify(error={"code": "not_found", "message": "User not found"}), 404
    return jsonify(user=user.to_dict())
