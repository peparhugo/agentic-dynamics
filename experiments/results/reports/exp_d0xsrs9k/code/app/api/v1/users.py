import logging

from flask import Blueprint, g, jsonify, request

from app.middleware.auth import login_required, role_required
from app.middleware.rate_limit import rate_limit
from app.middleware.validation import validate_schema, validate_query_schema
from app.middleware.validation import UserUpdateSchema, UserQuerySchema
from app.models.user import User
from app.utils.errors import NotFoundError, ConflictError
from app.utils.pagination import paginate

logger = logging.getLogger("audit")
users_bp = Blueprint("users_v1", __name__, url_prefix="/api/v1/users")


@users_bp.route("", methods=["GET"])
@login_required
@validate_query_schema(UserQuerySchema)
def list_users():
    query = request.validated_query
    page = query["page"]
    per_page = query["per_page"]

    users, total = User.list_all(page=page, per_page=per_page)
    data = [u.to_dict() for u in users]
    result = paginate(data, total, page, per_page)

    return jsonify(result)


@users_bp.route("/<user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        raise NotFoundError("User not found", "user_not_found")
    return jsonify({"user": user.to_dict()})


@users_bp.route("/<user_id>", methods=["PUT"])
@login_required
@validate_schema(UserUpdateSchema)
def update_user(user_id):
    if g.current_user.role != "admin" and g.current_user.id != user_id:
        from app.middleware.auth import ForbiddenError
        raise ForbiddenError(
            "You can only update your own profile", "insufficient_permissions"
        )

    data = request.validated_data
    if not data:
        raise ConflictError("No fields to update", "no_fields")

    update_data = {k: v for k, v in data.items() if v is not None}

    if "role" in update_data and g.current_user.role != "admin":
        from app.middleware.auth import ForbiddenError
        raise ForbiddenError(
            "Only admins can change roles", "insufficient_permissions"
        )

    try:
        user = User.update(user_id, **update_data)
    except ValueError as e:
        raise ConflictError(str(e), "email_exists")

    if not user:
        raise NotFoundError("User not found", "user_not_found")

    logger.info(
        "User updated",
        extra={
            "audit_type": "user_update",
            "user_id": user.id,
            "email": user.email,
            "actor_id": g.current_user.id,
        },
    )

    return jsonify({"user": user.to_dict()})


@users_bp.route("/<user_id>", methods=["DELETE"])
@login_required
@role_required("admin")
def delete_user(user_id):
    if g.current_user.id == user_id:
        raise ConflictError(
            "Cannot delete your own account", "cannot_delete_self"
        )

    deleted = User.delete(user_id)
    if not deleted:
        raise NotFoundError("User not found", "user_not_found")

    logger.info(
        "User deleted",
        extra={
            "audit_type": "user_delete",
            "user_id": user_id,
            "actor_id": g.current_user.id,
        },
    )

    return jsonify({"message": "User deleted successfully"})
