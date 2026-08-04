from flask import Blueprint, request

from app.models.user import User
from app.utils.jwt import create_token, require_auth, require_role, get_current_user
from app.utils.validators import (
    LoginSchema,
    RegisterSchema,
    UserUpdateSchema,
    PaginationSchema,
    validate,
)
from app.utils.pagination import paginate
from app.middleware.audit import log_event

auth_bp = Blueprint("auth_v2", __name__, url_prefix="/api/v2/auth")
users_bp = Blueprint("users_v2", __name__, url_prefix="/api/v2/users")

# --- v2 Auth routes (with enhanced response envelope) ---


@auth_bp.route("/register", methods=["POST"])
def register():
    data, error = validate(RegisterSchema, request.get_json(silent=True) or {})
    if error:
        return {"success": False, **error}, 400

    try:
        user = User.create(
            username=data["username"],
            email=data["email"],
            password=data["password"],
        )
    except ValueError as e:
        return {"success": False, "error": str(e)}, 409

    log_event("register_v2", resource="user", resource_id=user.id, status_code=201)
    token = create_token(user.id, user.role)
    return {"success": True, "data": {"user": user.to_dict(), "token": token}}, 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data, error = validate(LoginSchema, request.get_json(silent=True) or {})
    if error:
        return {"success": False, **error}, 400

    user = User.get_by_username(data["username"])
    if not user or not user.verify_password(data["password"]):
        log_event("login_failed_v2", resource="auth", status_code=401)
        return {"success": False, "error": "Invalid username or password"}, 401

    log_event("login_v2", resource="user", resource_id=user.id, status_code=200)
    token = create_token(user.id, user.role)
    return {"success": True, "data": {"user": user.to_dict(), "token": token}}


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    user = get_current_user()
    return {"success": True, "data": {"user": user.to_dict()}}


# --- v2 User routes ---


@users_bp.route("", methods=["GET"])
@require_auth
def list_users():
    data, error = validate(PaginationSchema, dict(request.args))
    if error:
        return {"success": False, **error}, 400

    result = paginate(
        lambda **kw: User.list_all(**kw),
        sort_by=data.get("sort_by", "id"),
        order=data.get("order", "asc"),
    )
    return {"success": True, "data": result}


@users_bp.route("/<int:user_id>", methods=["GET"])
@require_auth
def get_user(user_id):
    user = User.get_by_id(user_id)
    if not user:
        return {"success": False, "error": "User not found"}, 404
    return {"success": True, "data": {"user": user.to_dict()}}


@users_bp.route("/<int:user_id>", methods=["PUT"])
@require_auth
def update_user(user_id):
    current = get_current_user()
    user = User.get_by_id(user_id)
    if not user:
        return {"success": False, "error": "User not found"}, 404
    if current.id != user.id and current.role != "admin":
        return {"success": False, "error": "Insufficient permissions"}, 403

    data, error = validate(UserUpdateSchema, request.get_json(silent=True) or {})
    if error:
        return {"success": False, **error}, 400

    if "role" in data and data["role"] is not None and current.role != "admin":
        return {"success": False, "error": "Only admins can change roles"}, 403

    updated = User.update(user_id, **data)
    log_event("update_user_v2", resource="user", resource_id=user_id, status_code=200)
    return {"success": True, "data": {"user": updated.to_dict()}}


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_user(user_id):
    user = User.delete(user_id)
    if not user:
        return {"success": False, "error": "User not found"}, 404
    log_event("delete_user_v2", resource="user", resource_id=user_id, status_code=200)
    return {"success": True, "data": {"message": "User deleted"}}
