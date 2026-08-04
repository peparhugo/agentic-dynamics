from flask import Blueprint, request, g

from auth.jwt import login_required, admin_required, create_token
from models.user import User
from validators.schemas import RegisterSchema, LoginSchema, UserUpdateSchema, PaginationSchema
from middleware.audit import log_audit
from middleware.rate_limiter import limiter
from utils.pagination import paginate

v2 = Blueprint("v2", __name__, url_prefix="/api/v2")
register_schema = RegisterSchema()
login_schema = LoginSchema()
update_schema = UserUpdateSchema()
pagination_schema = PaginationSchema()


@v2.route("/auth/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data = register_schema.load(request.get_json(silent=True) or {})
    try:
        user = User.create(data["name"], data["email"], data["password"], data["role"])
    except ValueError as e:
        log_audit("register", email=data["email"], status="failed", details={"reason": str(e), "version": "v2"})
        return {"error": str(e)}, 409
    log_audit("register", user=user.email, status="success", details={"version": "v2"})
    token = create_token(user.email)
    return {"token": token, "user": user.to_dict()}, 201


@v2.route("/auth/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = login_schema.load(request.get_json(silent=True) or {})
    user = User.find_by_email(data["email"])
    if not user or not user.check_password(data["password"]):
        log_audit("login", email=data["email"], status="failed", details={"version": "v2"})
        return {"error": "Invalid email or password"}, 401
    log_audit("login", user=user.email, status="success", details={"version": "v2"})
    token = create_token(user.email)
    return {"token": token, "user": user.to_dict()}, 200


@v2.route("/users", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def list_users():
    log_audit("list_users", user=g.current_user.email, status="success", details={"version": "v2"})
    users = User.list_all()
    return paginate(users), 200


@v2.route("/users/<user_id>", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        log_audit("get_user", user=g.current_user.email, status="failed", details={"user_id": user_id, "version": "v2"})
        return {"error": "User not found"}, 404
    log_audit("get_user", user=g.current_user.email, status="success", details={"user_id": user_id, "version": "v2"})
    return user.to_dict(), 200


@v2.route("/users/<user_id>", methods=["PATCH"])
@login_required
@limiter.limit("30 per minute")
def update_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        log_audit("update_user", user=g.current_user.email, status="failed", details={"user_id": user_id, "version": "v2"})
        return {"error": "User not found"}, 404

    if user.id != g.current_user.id and g.current_user.role != "admin":
        log_audit("update_user", user=g.current_user.email, status="forbidden", details={"user_id": user_id, "version": "v2"})
        return {"error": "Forbidden"}, 403

    data = update_schema.load(request.get_json(silent=True) or {})
    if "name" in data:
        user.name = data["name"]
    if "role" in data and g.current_user.role == "admin":
        user.role = data["role"]
    from datetime import datetime, timezone
    user.updated_at = datetime.now(timezone.utc)
    log_audit("update_user", user=g.current_user.email, status="success", details={"user_id": user_id, "version": "v2"})
    return user.to_dict(), 200


@v2.route("/users/<user_id>", methods=["DELETE"])
@admin_required
@limiter.limit("10 per minute")
def delete_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        log_audit("delete_user", user=g.current_user.email, status="failed", details={"user_id": user_id, "version": "v2"})
        return {"error": "User not found"}, 404
    User.delete(user.email)
    log_audit("delete_user", user=g.current_user.email, status="success", details={"deleted": user.email, "version": "v2"})
    return {"message": "User deleted"}, 200
