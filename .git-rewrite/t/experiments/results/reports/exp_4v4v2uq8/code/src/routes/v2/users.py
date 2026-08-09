from flask import Blueprint, request, g

from ...models import user_store
from ...middleware.auth import require_auth, optional_auth
from ...middleware.rate_limit import rate_limit
from ...middleware.audit import audit_log
from ...validation.schemas import CreateUserSchemaV2, UpdateUserSchemaV2
from ...utils.pagination import paginate

v2_users_bp = Blueprint("v2_users", __name__)


@v2_users_bp.route("", methods=["GET"])
@rate_limit
def list_users():
    users = user_store.list_all()
    result = paginate(users)
    result["data"] = [u.to_dict() for u in result["data"]]
    result["meta"] = {"version": "v2"}
    return result, 200


@v2_users_bp.route("/<user_id>", methods=["GET"])
@rate_limit
def get_user(user_id):
    user = user_store.get_by_id(user_id)
    if user is None:
        return {"error": "User not found", "code": "USER_NOT_FOUND"}, 404
    return {"data": user.to_dict(), "meta": {"version": "v2"}}, 200


@v2_users_bp.route("", methods=["POST"])
@rate_limit
@audit_log(action_override="register", resource_override="users")
def create_user():
    schema = CreateUserSchemaV2()
    data = schema.load(request.get_json(silent=True) or {})

    if user_store.get_by_username(data["username"]):
        return {"error": "Username already taken", "code": "USERNAME_TAKEN"}, 409
    if user_store.get_by_email(data["email"]):
        return {"error": "Email already taken", "code": "EMAIL_TAKEN"}, 409

    user = user_store.create(
        username=data["username"],
        email=data["email"],
        password=data["password"],
        role=data.get("role", "user"),
    )

    return {"data": user.to_dict(), "meta": {"version": "v2"}}, 201


@v2_users_bp.route("/<user_id>", methods=["PUT"])
@require_auth
@rate_limit
@audit_log(action_override="update", resource_override="users")
def update_user(user_id):
    if g.current_user_id != user_id and g.current_user_role != "admin":
        return {"error": "Forbidden", "code": "FORBIDDEN"}, 403

    schema = UpdateUserSchemaV2()
    data = schema.load(request.get_json(silent=True) or {})

    if "username" in data:
        existing = user_store.get_by_username(data["username"])
        if existing and existing.id != user_id:
            return {"error": "Username already taken", "code": "USERNAME_TAKEN"}, 409

    if "email" in data:
        existing = user_store.get_by_email(data["email"])
        if existing and existing.id != user_id:
            return {"error": "Email already taken", "code": "EMAIL_TAKEN"}, 409

    user = user_store.update(user_id, **data)
    if user is None:
        return {"error": "User not found", "code": "USER_NOT_FOUND"}, 404

    return {"data": user.to_dict(), "meta": {"version": "v2"}}, 200


@v2_users_bp.route("/<user_id>", methods=["DELETE"])
@require_auth
@rate_limit
@audit_log(action_override="delete", resource_override="users")
def delete_user(user_id):
    if g.current_user_id != user_id and g.current_user_role != "admin":
        return {"error": "Forbidden", "code": "FORBIDDEN"}, 403

    if not user_store.delete(user_id):
        return {"error": "User not found", "code": "USER_NOT_FOUND"}, 404

    return {"data": {"message": "User deleted"}, "meta": {"version": "v2"}}, 200
