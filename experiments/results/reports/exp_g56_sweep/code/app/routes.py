from datetime import datetime, timezone
from math import ceil

from flask import Blueprint, current_app, g, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import decode_token, hash_jti, issue_token_pair, require_auth
from .errors import APIError
from .models import AuditLog, Item, RefreshToken, User
from .validation import (
    json_body,
    pagination_args,
    validate_email,
    validate_item,
    validate_password,
)


api = Blueprint("api", __name__)


def session():
    return current_app.extensions["db_session"]


def client_ip():
    return request.remote_addr or "unknown"


def audit(action, resource_type, resource_id=None, actor_id=None):
    session().add(
        AuditLog(
            actor_id=actor_id if actor_id is not None else g.current_user.id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_address=client_ip(),
        )
    )


def item_json(item):
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def audit_json(entry):
    return {
        "id": entry.id,
        "action": entry.action,
        "resource_type": entry.resource_type,
        "resource_id": entry.resource_id,
        "ip_address": entry.ip_address,
        "created_at": entry.created_at.isoformat(),
    }


def paginated(query, serializer):
    page, per_page = pagination_args()
    db = session()
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.offset((page - 1) * per_page).limit(per_page)).all()
    return {
        "items": [serializer(row) for row in rows],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": ceil(total / per_page) if total else 0,
        },
    }


@api.get("/health")
def health():
    if request.args:
        raise APIError(400, "validation_error", "Health endpoint accepts no parameters")
    return {"status": "ok"}


@api.post("/auth/register")
def register():
    data = json_body({"email", "password"}, {"email", "password"})
    email = validate_email(data["email"])
    password = validate_password(data["password"])
    db = session()
    user = User(email=email, password_hash=generate_password_hash(password))
    db.add(user)
    try:
        db.flush()
        audit("register", "user", user.id, actor_id=user.id)
        tokens = issue_token_pair(user.id, db)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise APIError(409, "email_exists", "An account with this email already exists") from exc
    return {"user": {"id": user.id, "email": user.email}, **tokens}, 201


@api.post("/auth/login")
def login():
    allowed, retry_after = current_app.extensions["login_rate_limiter"].check(client_ip())
    if not allowed:
        raise APIError(
            429,
            "rate_limit_exceeded",
            "Too many login attempts",
            headers={"Retry-After": str(retry_after)},
        )
    data = json_body({"email", "password"}, {"email", "password"})
    email = validate_email(data["email"])
    password = validate_password(data["password"])
    db = session()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not check_password_hash(user.password_hash, password):
        raise APIError(401, "invalid_credentials", "Email or password is incorrect")
    tokens = issue_token_pair(user.id, db)
    audit("login", "user", user.id, actor_id=user.id)
    db.commit()
    return tokens


@api.post("/auth/refresh")
def refresh():
    data = json_body({"refresh_token"}, {"refresh_token"})
    if not isinstance(data["refresh_token"], str) or not data["refresh_token"]:
        raise APIError(400, "validation_error", "Refresh token must be a string")
    payload = decode_token(data["refresh_token"], "refresh")
    db = session()
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(payload["jti"]))
    )
    if stored is None or stored.revoked:
        raise APIError(401, "invalid_token", "Refresh token is revoked or unknown")
    if stored.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise APIError(401, "token_expired", "Token has expired")
    stored.revoked = True
    tokens = issue_token_pair(stored.user_id, db)
    audit("refresh", "token", stored.id, actor_id=stored.user_id)
    db.commit()
    return tokens


@api.post("/auth/logout")
@require_auth
def logout():
    data = json_body({"refresh_token"}, {"refresh_token"})
    if not isinstance(data["refresh_token"], str) or not data["refresh_token"]:
        raise APIError(400, "validation_error", "Refresh token must be a string")
    payload = decode_token(data["refresh_token"], "refresh")
    db = session()
    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.jti_hash == hash_jti(payload["jti"]))
    )
    if stored is None or stored.revoked or stored.user_id != g.current_user.id:
        raise APIError(401, "invalid_token", "Refresh token is revoked or unknown")
    stored.revoked = True
    audit("logout", "token", stored.id)
    db.commit()
    return "", 204


@api.get("/items")
@require_auth
def list_items():
    query = (
        select(Item)
        .where(Item.owner_id == g.current_user.id)
        .order_by(Item.id.asc())
    )
    return paginated(query, item_json)


@api.post("/items")
@require_auth
def create_item():
    data = validate_item(json_body({"name", "description"}, {"name"}))
    item = Item(owner_id=g.current_user.id, **data)
    db = session()
    db.add(item)
    db.flush()
    audit("create", "item", item.id)
    db.commit()
    return item_json(item), 201


def owned_item(item_id):
    item = session().scalar(
        select(Item).where(Item.id == item_id, Item.owner_id == g.current_user.id)
    )
    if item is None:
        raise APIError(404, "not_found", "Item was not found")
    return item


@api.get("/items/<int:item_id>")
@require_auth
def get_item(item_id):
    if request.args:
        raise APIError(400, "validation_error", "Item endpoint accepts no parameters")
    return item_json(owned_item(item_id))


@api.patch("/items/<int:item_id>")
@require_auth
def update_item(item_id):
    data = validate_item(json_body({"name", "description"}), partial=True)
    item = owned_item(item_id)
    for key, value in data.items():
        setattr(item, key, value)
    audit("update", "item", item.id)
    session().commit()
    return item_json(item)


@api.delete("/items/<int:item_id>")
@require_auth
def delete_item(item_id):
    if request.args:
        raise APIError(400, "validation_error", "Delete endpoint accepts no parameters")
    item = owned_item(item_id)
    db = session()
    audit("delete", "item", item.id)
    db.delete(item)
    db.commit()
    return "", 204


@api.get("/audit-logs")
@require_auth
def list_audit_logs():
    query = (
        select(AuditLog)
        .where(AuditLog.actor_id == g.current_user.id)
        .order_by(AuditLog.id.asc())
    )
    return paginated(query, audit_json)
