from datetime import datetime, timedelta
from flask import Blueprint, request, g, current_app
from app import db
from app.models import User, RefreshToken as RefreshTokenModel, AuditLog
from app.auth import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    login_required,
)
from app.validators import (
    RegisterSchema,
    LoginSchema,
    RefreshSchema,
    UpdateUserSchema,
    validate,
)
from app.middleware import rate_limit
from app.audit import log_audit, flush_audit_logs

bp = Blueprint("v1", __name__)


@bp.errorhandler(400)
def bad_request(e):
    return {"error": "Bad request"}, 400


@bp.errorhandler(404)
def not_found(e):
    return {"error": "Not found"}, 404


@bp.errorhandler(405)
def method_not_allowed(e):
    return {"error": "Method not allowed"}, 405


@bp.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return {"error": "Internal server error"}, 500


def _paginate(query):
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except (ValueError, TypeError):
        page = 1
        per_page = 20

    if page < 1:
        page = 1
    per_page = max(1, min(per_page, 100))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "data": [item.to_dict() for item in pagination.items],
        "pagination": {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev,
        },
    }


@bp.route("/auth/register", methods=["POST"])
@validate(RegisterSchema)
def register(data):
    if User.query.filter(
        db.or_(User.email == data["email"], User.username == data["username"])
    ).first():
        return {"error": "Username or email already exists"}, 409

    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    log_audit("register", "user", resource_id=user.id)
    flush_audit_logs()

    access_token = generate_access_token(user.id)
    refresh_jwt, refresh_token_raw = generate_refresh_token(user.id)

    rt = RefreshTokenModel(
        user_id=user.id,
        token=refresh_token_raw,
        expires_at=datetime.utcnow() + timedelta(
            days=current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"]
        ),
    )
    db.session.add(rt)
    db.session.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_jwt,
        "user": user.to_dict(),
    }, 201


@bp.route("/auth/login", methods=["POST"])
@rate_limit(5, 60)
@validate(LoginSchema)
def login(data):
    user = User.query.filter_by(email=data["email"]).first()
    if user is None or not user.check_password(data["password"]):
        return {"error": "Invalid email or password"}, 401

    access_token = generate_access_token(user.id)
    refresh_jwt, refresh_token_raw = generate_refresh_token(user.id)

    rt = RefreshTokenModel(
        user_id=user.id,
        token=refresh_token_raw,
        expires_at=datetime.utcnow() + timedelta(
            days=current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"]
        ),
    )
    db.session.add(rt)
    db.session.commit()

    log_audit("login", "user", resource_id=user.id)
    flush_audit_logs()

    return {
        "access_token": access_token,
        "refresh_token": refresh_jwt,
        "user": user.to_dict(),
    }, 200


@bp.route("/auth/refresh", methods=["POST"])
@validate(RefreshSchema)
def refresh(data):
    payload = decode_token(data["refresh_token"])
    if payload is None:
        return {"error": "Invalid or expired refresh token"}, 401
    if payload.get("type") != "refresh":
        return {"error": "Invalid token type"}, 401

    user = User.query.get(payload["sub"])
    if user is None:
        return {"error": "User not found"}, 401

    rt = RefreshTokenModel.query.filter_by(token=payload.get("jti", ""), revoked=False).first()
    if rt is None:
        return {"error": "Refresh token revoked or not found"}, 401

    if rt.expires_at < datetime.utcnow():
        rt.revoked = True
        db.session.commit()
        return {"error": "Refresh token expired"}, 401

    rt.revoked = True
    db.session.commit()

    access_token = generate_access_token(user.id)
    new_refresh_jwt, new_refresh_token_raw = generate_refresh_token(user.id)

    new_rt = RefreshTokenModel(
        user_id=user.id,
        token=new_refresh_token_raw,
        expires_at=datetime.utcnow() + timedelta(
            days=current_app.config["JWT_REFRESH_TOKEN_EXPIRE_DAYS"]
        ),
    )
    db.session.add(new_rt)
    db.session.commit()

    log_audit("refresh_token", "auth", resource_id=user.id)
    flush_audit_logs()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_jwt,
    }, 200


@bp.route("/auth/logout", methods=["POST"])
@login_required
def logout():
    RefreshTokenModel.query.filter_by(user_id=g.current_user.id).update({"revoked": True})
    db.session.commit()

    log_audit("logout", "user", resource_id=g.current_user.id)
    flush_audit_logs()

    return {"message": "Logged out successfully"}, 200


@bp.route("/users", methods=["GET"])
@login_required
def list_users():
    query = User.query.order_by(User.id)
    result = _paginate(query)
    return result, 200


@bp.route("/users/<int:user_id>", methods=["GET"])
@login_required
def get_user(user_id):
    user = User.query.get(user_id)
    if user is None:
        return {"error": "User not found"}, 404
    return {"data": user.to_dict()}, 200


@bp.route("/users/<int:user_id>", methods=["PUT"])
@login_required
@validate(UpdateUserSchema)
def update_user(data, user_id):
    if g.current_user.id != user_id:
        return {"error": "Forbidden"}, 403

    user = User.query.get(user_id)
    if user is None:
        return {"error": "User not found"}, 404

    if "username" in data:
        if User.query.filter(User.username == data["username"], User.id != user_id).first():
            return {"error": "Username already taken"}, 409
        user.username = data["username"]
    if "email" in data:
        if User.query.filter(User.email == data["email"], User.id != user_id).first():
            return {"error": "Email already taken"}, 409
        user.email = data["email"]
    if "password" in data:
        user.set_password(data["password"])

    db.session.commit()
    log_audit("update", "user", resource_id=user.id)
    flush_audit_logs()

    return {"data": user.to_dict()}, 200


@bp.route("/users/<int:user_id>", methods=["DELETE"])
@login_required
def delete_user(user_id):
    if g.current_user.id != user_id:
        return {"error": "Forbidden"}, 403

    user = User.query.get(user_id)
    if user is None:
        return {"error": "User not found"}, 404

    RefreshTokenModel.query.filter_by(user_id=user_id).delete()
    AuditLog.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()

    log_audit("delete", "user", resource_id=user_id)
    flush_audit_logs()

    return {"message": "User deleted successfully"}, 200
