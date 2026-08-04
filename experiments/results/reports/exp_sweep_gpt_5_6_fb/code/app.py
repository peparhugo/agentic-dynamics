import os
import uuid
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address, default_limits=[])


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(1000), nullable=False, default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    action = db.Column(db.String(40), nullable=False)
    resource_type = db.Column(db.String(40), nullable=False)
    resource_id = db.Column(db.String(64), nullable=True)
    ip_address = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RevokedToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)


def error(message, status, details=None):
    body = {"error": {"message": message, "status": status}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def json_body(required=None, allowed=None):
    if not request.is_json:
        return None, error("Content-Type must be application/json", 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error("Request body must be a JSON object", 400)
    required = required or set()
    allowed = allowed or required
    missing = sorted(required - data.keys())
    unknown = sorted(data.keys() - allowed)
    if missing or unknown:
        details = {}
        if missing:
            details["missing"] = missing
        if unknown:
            details["unknown"] = unknown
        return None, error("Invalid request body", 400, details)
    return data, None


def valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and "@" in value and value.index("@") > 0 and value.rindex("@") < len(value) - 1


def serialize_item(item):
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "owner_id": item.owner_id,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def audit(action, resource_type, resource_id=None, user_id=None):
    db.session.add(AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=request.remote_addr or "unknown",
    ))


def current_user_id():
    return int(get_jwt_identity())


def pagination():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except (TypeError, ValueError):
        return None, error("page and per_page must be integers", 400)
    if page < 1 or per_page < 1 or per_page > 100:
        return None, error("page must be at least 1 and per_page must be between 1 and 100", 400)
    unknown = set(request.args) - {"page", "per_page"}
    if unknown:
        return None, error("Unknown query parameters", 400, {"unknown": sorted(unknown)})
    return (page, per_page), None


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///api.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "development-only-change-me"),
        JWT_ACCESS_TOKEN_EXPIRES=900,
        JWT_REFRESH_TOKEN_EXPIRES=2592000,
        RATELIMIT_STORAGE_URI="memory://",
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    @jwt.token_in_blocklist_loader
    def token_revoked(_, payload):
        return db.session.scalar(db.select(RevokedToken.id).where(RevokedToken.jti == payload["jti"])) is not None

    @jwt.unauthorized_loader
    def unauthorized(message):
        return error(message, 401)

    @jwt.invalid_token_loader
    def invalid_token(message):
        return error(message, 401)

    @jwt.expired_token_loader
    def expired_token(_, __):
        return error("Token has expired", 401)

    @jwt.revoked_token_loader
    def revoked_token(_, __):
        return error("Token has been revoked", 401)

    @jwt.needs_fresh_token_loader
    def fresh_token(_, __):
        return error("Fresh token required", 401)

    @app.errorhandler(429)
    def rate_limited(_):
        return error("Rate limit exceeded", 429)

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return error(exc.description, exc.code)

    @app.errorhandler(Exception)
    def internal_error(exc):
        db.session.rollback()
        app.logger.exception(exc)
        return error("Internal server error", 500)

    @app.post("/v1/auth/register")
    def register():
        data, failure = json_body({"email", "password"})
        if failure:
            return failure
        email = data["email"].strip().lower() if isinstance(data["email"], str) else data["email"]
        password = data["password"]
        details = {}
        if not valid_email(email):
            details["email"] = "must be a valid email address"
        if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
            details["password"] = "must be between 8 and 128 characters"
        if details:
            return error("Validation failed", 422, details)
        user = User(email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            return error("Email is already registered", 409)
        audit("create", "user", user.id, user.id)
        db.session.commit()
        return jsonify({"id": user.id, "email": user.email, "created_at": user.created_at.isoformat()}), 201

    @app.post("/v1/auth/login")
    @limiter.limit("5 per minute")
    def login():
        data, failure = json_body({"email", "password"})
        if failure:
            return failure
        if not isinstance(data["email"], str) or not isinstance(data["password"], str):
            return error("Email and password must be strings", 422)
        user = db.session.scalar(db.select(User).where(User.email == data["email"].strip().lower()))
        if user is None or not check_password_hash(user.password_hash, data["password"]):
            return error("Invalid credentials", 401)
        audit("login", "session", user_id=user.id)
        db.session.commit()
        return jsonify({
            "access_token": create_access_token(identity=str(user.id), fresh=True),
            "refresh_token": create_refresh_token(identity=str(user.id)),
            "token_type": "Bearer",
        })

    @app.post("/v1/auth/refresh")
    @jwt_required(refresh=True)
    def refresh():
        if request.content_length not in (None, 0):
            data, failure = json_body(set(), set())
            if failure:
                return failure
            if data:
                return error("Request body must be empty", 400)
        user_id = current_user_id()
        token = get_jwt()
        db.session.add(RevokedToken(jti=token["jti"], expires_at=datetime.fromtimestamp(token["exp"], timezone.utc)))
        audit("refresh", "session", user_id=user_id)
        db.session.commit()
        return jsonify({
            "access_token": create_access_token(identity=str(user_id), fresh=False),
            "refresh_token": create_refresh_token(identity=str(user_id)),
            "token_type": "Bearer",
        })

    @app.delete("/v1/auth/logout")
    @jwt_required(verify_type=False)
    def logout():
        token = get_jwt()
        db.session.add(RevokedToken(jti=token["jti"], expires_at=datetime.fromtimestamp(token["exp"], timezone.utc)))
        audit("logout", "session", user_id=current_user_id())
        db.session.commit()
        return "", 204

    @app.get("/v1/users/me")
    @jwt_required()
    def me():
        user = db.session.get(User, current_user_id())
        if user is None:
            return error("User not found", 404)
        return jsonify({"id": user.id, "email": user.email, "created_at": user.created_at.isoformat()})

    @app.get("/v1/items")
    @jwt_required()
    def list_items():
        values, failure = pagination()
        if failure:
            return failure
        page, per_page = values
        query = db.select(Item).where(Item.owner_id == current_user_id()).order_by(Item.id)
        result = db.paginate(query, page=page, per_page=per_page, error_out=False)
        return jsonify({
            "items": [serialize_item(item) for item in result.items],
            "pagination": {"page": page, "per_page": per_page, "total": result.total, "pages": result.pages},
        })

    @app.post("/v1/items")
    @jwt_required()
    def create_item():
        data, failure = json_body({"name"}, {"name", "description"})
        if failure:
            return failure
        name = data["name"].strip() if isinstance(data["name"], str) else data["name"]
        description = data.get("description", "")
        details = {}
        if not isinstance(name, str) or not name or len(name) > 120:
            details["name"] = "must be a non-empty string of at most 120 characters"
        if not isinstance(description, str) or len(description) > 1000:
            details["description"] = "must be a string of at most 1000 characters"
        if details:
            return error("Validation failed", 422, details)
        item = Item(name=name, description=description, owner_id=current_user_id())
        db.session.add(item)
        db.session.flush()
        audit("create", "item", item.id, item.owner_id)
        db.session.commit()
        return jsonify(serialize_item(item)), 201

    @app.get("/v1/items/<int:item_id>")
    @jwt_required()
    def get_item(item_id):
        item = db.session.get(Item, item_id)
        if item is None or item.owner_id != current_user_id():
            return error("Item not found", 404)
        return jsonify(serialize_item(item))

    @app.patch("/v1/items/<int:item_id>")
    @jwt_required()
    def update_item(item_id):
        data, failure = json_body(set(), {"name", "description"})
        if failure:
            return failure
        if not data:
            return error("At least one field is required", 400)
        item = db.session.get(Item, item_id)
        if item is None or item.owner_id != current_user_id():
            return error("Item not found", 404)
        details = {}
        if "name" in data and (not isinstance(data["name"], str) or not data["name"].strip() or len(data["name"].strip()) > 120):
            details["name"] = "must be a non-empty string of at most 120 characters"
        if "description" in data and (not isinstance(data["description"], str) or len(data["description"]) > 1000):
            details["description"] = "must be a string of at most 1000 characters"
        if details:
            return error("Validation failed", 422, details)
        if "name" in data:
            item.name = data["name"].strip()
        if "description" in data:
            item.description = data["description"]
        item.updated_at = datetime.now(timezone.utc)
        audit("update", "item", item.id, item.owner_id)
        db.session.commit()
        return jsonify(serialize_item(item))

    @app.delete("/v1/items/<int:item_id>")
    @jwt_required()
    def delete_item(item_id):
        item = db.session.get(Item, item_id)
        if item is None or item.owner_id != current_user_id():
            return error("Item not found", 404)
        owner_id = item.owner_id
        audit("delete", "item", item.id, owner_id)
        db.session.delete(item)
        db.session.commit()
        return "", 204

    @app.get("/v1/audit-logs")
    @jwt_required()
    def list_audit_logs():
        values, failure = pagination()
        if failure:
            return failure
        page, per_page = values
        query = db.select(AuditLog).where(AuditLog.user_id == current_user_id()).order_by(AuditLog.id.desc())
        result = db.paginate(query, page=page, per_page=per_page, error_out=False)
        return jsonify({
            "items": [{
                "id": row.id,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "ip_address": row.ip_address,
                "created_at": row.created_at.isoformat(),
            } for row in result.items],
            "pagination": {"page": page, "per_page": per_page, "total": result.total, "pages": result.pages},
        })

    with app.app_context():
        db.create_all()
    return app


app = create_app()


if __name__ == "__main__":
    app.run()
