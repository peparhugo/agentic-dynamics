from flask import Blueprint, request, g

from auth.jwt import login_required, admin_required, create_token
from models.user import User
from validators.schemas import RegisterSchema, LoginSchema, PaginationSchema
from middleware.audit import log_audit
from middleware.rate_limiter import limiter
from utils.pagination import paginate

v1 = Blueprint("v1", __name__, url_prefix="/api/v1")
register_schema = RegisterSchema()
login_schema = LoginSchema()
pagination_schema = PaginationSchema()


@v1.route("/auth/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data = register_schema.load(request.get_json(silent=True) or {})
    try:
        user = User.create(data["name"], data["email"], data["password"], data["role"])
    except ValueError as e:
        log_audit("register", email=data["email"], status="failed", details={"reason": str(e)})
        return {"error": str(e)}, 409
    log_audit("register", user=user.email, status="success")
    token = create_token(user.email)
    return {"token": token, "user": user.to_dict()}, 201


@v1.route("/auth/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = login_schema.load(request.get_json(silent=True) or {})
    user = User.find_by_email(data["email"])
    if not user or not user.check_password(data["password"]):
        log_audit("login", email=data["email"], status="failed")
        return {"error": "Invalid email or password"}, 401
    log_audit("login", user=user.email, status="success")
    token = create_token(user.email)
    return {"token": token, "user": user.to_dict()}, 200


@v1.route("/users", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def list_users():
    log_audit("list_users", user=g.current_user.email, status="success")
    return paginate(User.list_all()), 200


@v1.route("/users/<user_id>", methods=["GET"])
@login_required
@limiter.limit("30 per minute")
def get_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        log_audit("get_user", user=g.current_user.email, status="failed", details={"user_id": user_id})
        return {"error": "User not found"}, 404
    log_audit("get_user", user=g.current_user.email, status="success", details={"user_id": user_id})
    return user.to_dict(), 200


@v1.route("/users/<user_id>", methods=["DELETE"])
@admin_required
@limiter.limit("10 per minute")
def delete_user(user_id):
    user = User.find_by_id(user_id)
    if not user:
        log_audit("delete_user", user=g.current_user.email, status="failed", details={"user_id": user_id})
        return {"error": "User not found"}, 404
    User.delete(user.email)
    log_audit("delete_user", user=g.current_user.email, status="success", details={"deleted": user.email})
    return {"message": "User deleted"}, 200
