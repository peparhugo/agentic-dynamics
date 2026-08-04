from flask import Blueprint, request, jsonify

from app.auth import require_auth
from app.middleware.rate_limiter import limiter
from app.models.user import User
from app.schemas.user import UserCreateSchema, UserUpdateSchema
from app.utils.helpers import build_paginated_response, parse_pagination_params

bp = Blueprint("users_v1", __name__, url_prefix="/api/v1/users")

user_create_schema = UserCreateSchema()
user_update_schema = UserUpdateSchema()


@bp.route("", methods=["GET"])
@require_auth
@limiter.limit("30 per minute")
def list_users():
    params = parse_pagination_params()
    users, total = User.list_all(
        offset=params["offset"],
        limit=params["per_page"],
        sort_by=params["sort_by"],
        order=params["order"],
    )
    return (
        jsonify(build_paginated_response(
            [u.to_dict() for u in users],
            total,
            params["page"],
            params["per_page"],
        )),
        200,
    )


@bp.route("/<user_id>", methods=["GET"])
@require_auth
@limiter.limit("30 per minute")
def get_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"data": user.to_dict()}), 200


@bp.route("", methods=["POST"])
@require_auth
@limiter.limit("10 per minute")
def create_user():
    data = user_create_schema.load(request.get_json() or {})
    try:
        user = User.create(
            email=data["email"],
            password=data["password"],
            name=data["name"],
            role=data.get("role", "user"),
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"data": user.to_dict()}), 201


@bp.route("/<user_id>", methods=["PATCH"])
@require_auth
@limiter.limit("20 per minute")
def update_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = user_update_schema.load(request.get_json() or {})
    updated = User.update(user_id, **data)
    return jsonify({"data": updated.to_dict()}), 200


@bp.route("/<user_id>", methods=["DELETE"])
@require_auth
@limiter.limit("10 per minute")
def delete_user(user_id):
    deleted = User.delete(user_id)
    if not deleted:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"data": {"deleted": True}}), 200
