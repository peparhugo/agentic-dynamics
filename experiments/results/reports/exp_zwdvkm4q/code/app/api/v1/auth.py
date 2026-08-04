from flask import Blueprint, request

from app.models.user import User
from app.utils.jwt import create_token, require_auth, require_role, get_current_user
from app.utils.validators import LoginSchema, RegisterSchema, UserUpdateSchema, validate
from app.middleware.audit import log_event

auth_bp = Blueprint("auth_v1", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data, error = validate(RegisterSchema, request.get_json(silent=True) or {})
    if error:
        return error, 400

    try:
        user = User.create(
            username=data["username"],
            email=data["email"],
            password=data["password"],
        )
    except ValueError as e:
        return {"error": str(e)}, 409

    log_event("register", resource="user", resource_id=user.id, status_code=201)
    token = create_token(user.id, user.role)
    return {"user": user.to_dict(), "token": token}, 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data, error = validate(LoginSchema, request.get_json(silent=True) or {})
    if error:
        return error, 400

    user = User.get_by_username(data["username"])
    if not user or not user.verify_password(data["password"]):
        log_event("login_failed", resource="auth", status_code=401)
        return {"error": "Invalid username or password"}, 401

    log_event("login", resource="user", resource_id=user.id, status_code=200)
    token = create_token(user.id, user.role)
    return {"user": user.to_dict(), "token": token}


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    user = get_current_user()
    return {"user": user.to_dict()}
