from flask import Blueprint, request, g

from ...models import user_store
from ...utils.token import create_access_token, create_refresh_token, decode_token
from ...middleware.rate_limit import rate_limit
from ...middleware.audit import audit_log
from ...validation.schemas import LoginSchema, RefreshSchema

v2_auth_bp = Blueprint("v2_auth", __name__)


@v2_auth_bp.route("/login", methods=["POST"])
@rate_limit
@audit_log(action_override="login", resource_override="auth")
def login():
    schema = LoginSchema()
    data = schema.load(request.get_json(silent=True) or {})
    user = user_store.get_by_username(data["username"])
    if user is None or not user_store.verify_password(user, data["password"]):
        return {"error": "Invalid credentials", "code": "INVALID_CREDENTIALS"}, 401
    if not user.is_active:
        return {"error": "Account is disabled", "code": "ACCOUNT_DISABLED"}, 403

    g.current_user_id = user.id
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, user.role)

    return {
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "user": user.to_dict(),
        },
        "meta": {"version": "v2"},
    }, 200


@v2_auth_bp.route("/refresh", methods=["POST"])
@rate_limit
@audit_log(action_override="refresh", resource_override="auth")
def refresh():
    schema = RefreshSchema()
    data = schema.load(request.get_json(silent=True) or {})

    try:
        payload = decode_token(data["refresh_token"])
        if payload.get("type") != "refresh":
            return {"error": "Invalid token type", "code": "INVALID_TOKEN_TYPE"}, 401
    except Exception:
        return {"error": "Invalid or expired refresh token", "code": "INVALID_TOKEN"}, 401

    user_id = payload["sub"]
    user = user_store.get_by_id(user_id)
    if user is None or not user.is_active:
        return {"error": "User not found or inactive", "code": "USER_NOT_FOUND"}, 404

    g.current_user_id = user.id
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id, user.role)

    return {
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
        },
        "meta": {"version": "v2"},
    }, 200
