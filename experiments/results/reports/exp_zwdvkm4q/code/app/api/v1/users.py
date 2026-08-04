from flask import Blueprint, request

from app.models.user import User
from app.utils.jwt import require_auth, require_role, get_current_user
from app.utils.validators import UserUpdateSchema, PaginationSchema, validate
from app.utils.pagination import paginate
from app.middleware.audit import log_event

users_bp = Blueprint("users_v1", __name__, url_prefix="/api/v1/users")


@users_bp.route("", methods=["GET"])
@require_auth
def list_users():
    data, error = validate(PaginationSchema, dict(request.args))
    if error:
        return error, 400

    result = paginate(
        lambda **kw: User.list_all(**kw),
        sort_by=data.get("sort_by", "id"),
        order=data.get("order", "asc"),
    )
    return result


@users_bp.route("/<int:user_id>", methods=["GET"])
@require_auth
def get_user(user_id):
    user = User.get_by_id(user_id)
    if not user:
        return {"error": "User not found"}, 404
    return {"user": user.to_dict()}


@users_bp.route("/<int:user_id>", methods=["PUT"])
@require_auth
def update_user(user_id):
    current = get_current_user()
    user = User.get_by_id(user_id)
    if not user:
        return {"error": "User not found"}, 404
    if current.id != user.id and current.role != "admin":
        return {"error": "Insufficient permissions"}, 403

    data, error = validate(UserUpdateSchema, request.get_json(silent=True) or {})
    if error:
        return error, 400

    if "role" in data and data["role"] is not None and current.role != "admin":
        return {"error": "Only admins can change roles"}, 403

    updated = User.update(user_id, **data)
    log_event("update_user", resource="user", resource_id=user_id, status_code=200)
    return {"user": updated.to_dict()}


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_user(user_id):
    user = User.delete(user_id)
    if not user:
        return {"error": "User not found"}, 404
    log_event("delete_user", resource="user", resource_id=user_id, status_code=200)
    return {"message": "User deleted"}
