"""Authentication endpoints: register, login, refresh, me."""
from flask import jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from ...audit import set_audit_action
from ...errors import ApiError
from ...extensions import db, limiter
from ...models import User
from ...schemas import LoginSchema, RegisterSchema
from . import bp


def _json_body() -> dict:
    if not request.is_json:
        raise ApiError(
            "Request body must be JSON.", status_code=415, code="unsupported_media_type"
        )
    return request.get_json(silent=True) or {}


def _tokens_for(user: User) -> dict:
    identity = str(user.id)
    claims = {"role": user.role}
    return {
        "access_token": create_access_token(identity=identity, additional_claims=claims),
        "refresh_token": create_refresh_token(identity=identity),
        "token_type": "Bearer",
    }


@bp.post("/auth/register")
@limiter.limit("10 per minute")
def register():
    data = RegisterSchema().load(_json_body())
    if User.query.filter_by(email=data["email"]).first():
        raise ApiError("Email already registered.", status_code=409, code="email_taken")
    user = User(email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    set_audit_action("auth.register", f"user={user.email}")
    return jsonify({"user": user.to_dict(), **_tokens_for(user)}), 201


@bp.post("/auth/login")
@limiter.limit("10 per minute")
def login():
    data = LoginSchema().load(_json_body())
    user = User.query.filter_by(email=data["email"]).first()
    if user is None or not user.check_password(data["password"]):
        set_audit_action("auth.login_failed", f"email={data['email']}")
        raise ApiError("Invalid email or password.", status_code=401, code="invalid_credentials")
    set_audit_action("auth.login", f"user={user.email}")
    return jsonify({"user": user.to_dict(), **_tokens_for(user)})


@bp.post("/auth/refresh")
@jwt_required(refresh=True)
@limiter.limit("30 per minute")
def refresh():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        raise ApiError("User no longer exists.", status_code=401, code="unknown_user")
    set_audit_action("auth.refresh", f"user={user.email}")
    return jsonify(
        {
            "access_token": create_access_token(
                identity=str(user.id), additional_claims={"role": user.role}
            ),
            "token_type": "Bearer",
        }
    )


@bp.get("/auth/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        raise ApiError("User no longer exists.", status_code=401, code="unknown_user")
    return jsonify({"user": user.to_dict()})
