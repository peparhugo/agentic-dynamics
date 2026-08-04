"""Authentication endpoints: register, login, refresh, me."""
from flask import current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)

from ...audit import audit
from ...errors import ConflictError, UnauthorizedError
from ...extensions import db, limiter
from ...models import User
from ...schemas import LoginSchema, RegisterSchema
from . import bp

_register_schema = RegisterSchema()
_login_schema = LoginSchema()


def _auth_limit():
    return current_app.config["RATELIMIT_AUTH"]


@bp.post("/auth/register")
@limiter.limit(_auth_limit)
def register():
    data = _register_schema.load(request.get_json(silent=True) or {})
    email = data["email"].lower().strip()

    if User.query.filter_by(email=email).first():
        raise ConflictError("A user with this email already exists.")

    user = User(email=email)
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()  # assign user.id for the audit entry
    audit("user.register", "user", user.id, user_id=user.id)
    db.session.commit()

    return jsonify({"data": user.to_dict()}), 201


@bp.post("/auth/login")
@limiter.limit(_auth_limit)
def login():
    data = _login_schema.load(request.get_json(silent=True) or {})
    email = data["email"].lower().strip()

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(data["password"]):
        audit("user.login_failed", "user", detail={"email": email})
        db.session.commit()
        raise UnauthorizedError("Invalid email or password.")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled.")

    identity = str(user.id)
    access = create_access_token(identity=identity)
    refresh = create_refresh_token(identity=identity)
    audit("user.login", "user", user.id, user_id=user.id)
    db.session.commit()

    return jsonify(
        {
            "data": {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "Bearer",
            }
        }
    )


@bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    user_id = int(get_jwt_identity())
    access = create_access_token(identity=str(user_id))
    audit("user.token_refresh", "user", user_id, user_id=user_id)
    db.session.commit()
    return jsonify({"data": {"access_token": access, "token_type": "Bearer"}})


@bp.get("/auth/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        raise UnauthorizedError("User no longer exists.")
    return jsonify({"data": user.to_dict()})
