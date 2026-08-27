import bcrypt
from flask import Blueprint, current_app, g, jsonify, request

from .audit import record_audit
from .decorators import token_required
from .errors import ConflictError, UnauthorizedError, ValidationError
from .extensions import db, limiter
from .models import User
from .security import (
    create_access_token,
    create_refresh_token,
    resolve_refresh_token,
)
from .validators import (
    get_json,
    require_fields,
    validate_email,
    validate_password,
    validate_username,
)

auth_bp = Blueprint("auth", __name__)


def _hash_password(password):
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password, password_hash):
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _auth_response(user):
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    }


@auth_bp.post("/register")
def register():
    data = get_json()
    require_fields(data, ["username", "email", "password"])
    validate_username(data["username"])
    validate_email(data["email"])
    validate_password(data["password"])

    username = data["username"]
    email = data["email"].lower()

    if User.query.filter((User.username == username) | (User.email == email)).first():
        raise ConflictError("Username or email already registered")

    user = User(
        username=username,
        email=email,
        password_hash=_hash_password(data["password"]),
        role="user",
    )
    db.session.add(user)
    db.session.flush()
    record_audit("auth.register", "user", user.id, {"username": username})
    db.session.commit()

    body = _auth_response(user)
    return jsonify(body), 201


@auth_bp.post("/login")
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"])
def login():
    data = get_json()
    require_fields(data, ["username", "password"])
    username = data["username"]
    password = data["password"]
    if not isinstance(username, str) or not isinstance(password, str):
        raise ValidationError("username and password must be strings")

    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).first()

    if user is None or not _check_password(password, user.password_hash):
        record_audit(
            "auth.login_failed",
            "user",
            user.id if user else None,
            {"username": username},
        )
        db.session.commit()
        raise UnauthorizedError("Invalid credentials")

    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    record_audit("auth.login", "user", user.id, {"username": user.username})
    db.session.commit()

    return jsonify(_auth_response(user)), 200


@auth_bp.post("/refresh")
def refresh():
    data = get_json()
    require_fields(data, ["refresh_token"])
    raw = data["refresh_token"]
    if not isinstance(raw, str) or not raw:
        raise ValidationError("refresh_token must be a non-empty string")

    record = resolve_refresh_token(raw)
    user = record.user
    record.revoked = True

    access_token = create_access_token(user)
    new_refresh_token = create_refresh_token(user)

    record_audit("auth.refresh", "user", user.id, {"username": user.username})
    db.session.commit()

    return (
        jsonify(
            {
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "Bearer",
            }
        ),
        200,
    )


@auth_bp.post("/logout")
@token_required
def logout():
    data = get_json()
    require_fields(data, ["refresh_token"])
    raw = data["refresh_token"]
    if not isinstance(raw, str) or not raw:
        raise ValidationError("refresh_token must be a non-empty string")

    record = resolve_refresh_token(raw)
    record.revoked = True
    record_audit("auth.logout", "user", g.current_user.id, {"username": g.current_user.username})
    db.session.commit()

    return jsonify({"message": "Successfully logged out"}), 200


@auth_bp.get("/me")
@token_required
def me():
    return jsonify(g.current_user.to_dict()), 200
