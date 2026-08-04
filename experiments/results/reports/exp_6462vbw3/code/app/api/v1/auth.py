from flask import Blueprint, request, g
from app.api.v1.schemas import RegisterSchema, LoginSchema
from app.middleware.auth import login_required
from app.middleware.validation import validate_json
from app.services.auth_service import register_user, login_user
from app.services.audit import log_audit

auth_bp = Blueprint("auth_v1", __name__, url_prefix="/api/v1/auth")


@auth_bp.route("/register", methods=["POST"])
@validate_json(RegisterSchema())
def register():
    data = request.validated_data
    resp, status = register_user(data["username"], data["email"], data["password"])
    if status == 201:
        log_audit("register", "user", None, f"User {data['username']} registered")
    return resp, status


@auth_bp.route("/login", methods=["POST"])
@validate_json(LoginSchema())
def login():
    data = request.validated_data
    resp, status = login_user(data["username"], data["password"])
    if status == 200:
        log_audit("login", "user", None, f"User {data['username']} logged in")
    return resp, status


@auth_bp.route("/me", methods=["GET"])
@login_required
def me():
    log_audit("profile_read", "user", g.current_user.id)
    return g.current_user.to_dict(), 200
