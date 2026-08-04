from flask import Blueprint, request, g
from app.extensions import db
from app.models.user import User
from app.api.v1.schemas import PaginationSchema, UserUpdateSchema
from app.middleware.auth import login_required, admin_required
from app.middleware.validation import validate_json, validate_query
from app.services.audit import log_audit
from app.utils.pagination import paginate

users_bp = Blueprint("users_v1", __name__, url_prefix="/api/v1/users")


@users_bp.route("", methods=["GET"])
@admin_required
@validate_query(PaginationSchema())
def list_users():
    args = request.validated_query
    query = User.query.order_by(User.created_at.desc())
    result = paginate(query, page=args["page"], per_page=args["per_page"])
    log_audit("list", "user")
    return result, 200


@users_bp.route("/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    if g.current_user.role != "admin" and g.current_user.id != user_id:
        return {"error": "Access denied"}, 403

    user = User.query.get(user_id)
    if user is None:
        return {"error": "User not found"}, 404

    log_audit("read", "user", user_id)
    return user.to_dict(), 200


@users_bp.route("/<int:user_id>", methods=["PUT"])
@admin_required
@validate_json(UserUpdateSchema())
def update_user(user_id):
    user = User.query.get(user_id)
    if user is None:
        return {"error": "User not found"}, 404

    data = request.validated_data
    for field in ["email", "role", "is_active"]:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    log_audit("update", "user", user_id)
    return user.to_dict(), 200


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    user = User.query.get(user_id)
    if user is None:
        return {"error": "User not found"}, 404

    db.session.delete(user)
    db.session.commit()
    log_audit("delete", "user", user_id)
    return {"message": "User deleted"}, 200
