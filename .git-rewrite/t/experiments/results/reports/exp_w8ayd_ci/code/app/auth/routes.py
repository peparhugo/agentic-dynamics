from flask import Blueprint, request, jsonify

from app.auth.jwt import create_access_token
from app.utils.serialization import login_schema
from app.middleware.validation import validate_request
from app.middleware.audit import audit_request, log_audit_event
from app.middleware.rate_limit import dynamic_rate_limit
from app.models.user import get_user_by_username
from app.utils.errors import AuthenticationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/auth/login", methods=["POST"])
@dynamic_rate_limit(limit_per_window=10, window_seconds=60)
@validate_request(login_schema)
@audit_request
def login():
    data = request.validated_data
    username = data["username"]
    password = data["password"]

    user = get_user_by_username(username)
    if user is None or not user.check_password(password):
        log_audit_event(
            action="LOGIN_FAILED",
            resource="/auth/login",
            details={"username": username, "reason": "invalid credentials"},
            status="failure",
        )
        raise AuthenticationError("Invalid username or password")

    token = create_access_token(user.id, roles=user.roles)
    log_audit_event(
        action="LOGIN_SUCCESS",
        resource="/auth/login",
        user_id=user.id,
        details={"username": user.username},
    )

    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "user": user.to_dict(),
    }), 200
