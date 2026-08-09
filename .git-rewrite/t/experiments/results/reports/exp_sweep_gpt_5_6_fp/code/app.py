import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import select
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

    def json(self):
        return {"id": self.id, "email": self.email, "created_at": iso(self.created_at)}


class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(1000), nullable=False, default="")
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def json(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "owner_id": self.owner_id,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }


class RefreshToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    revoked = db.Column(db.Boolean, nullable=False, default=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(40), nullable=False)
    resource = db.Column(db.String(40), nullable=False)
    resource_id = db.Column(db.String(64), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    def json(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "created_at": iso(self.created_at),
        }


def iso(value):
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def error(code, message, status, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def json_body(allowed, required=()):
    if not request.is_json:
        return None, error("invalid_content_type", "Content-Type must be application/json", 415)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, error("invalid_json", "Request body must be a JSON object", 400)
    details = {}
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        details["unknown"] = unknown
    missing = sorted(key for key in required if key not in data)
    if missing:
        details["missing"] = missing
    if details:
        return None, error("validation_error", "Invalid request data", 422, details)
    return data, None


def validate_email(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if len(value) > 254 or value.count("@") != 1:
        return None
    local, domain = value.split("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        return None
    return value


def pagination():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except (TypeError, ValueError):
        return None, error("validation_error", "Pagination values must be integers", 422)
    if page < 1 or per_page < 1 or per_page > 100:
        return None, error("validation_error", "page must be at least 1 and per_page must be between 1 and 100", 422)
    return (page, per_page), None


def paginated(query, serializer):
    values, failure = pagination()
    if failure:
        return failure
    page, per_page = values
    result = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return jsonify({
        "items": [serializer(item) for item in result.items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": result.total,
            "pages": result.pages,
            "has_next": result.has_next,
            "has_prev": result.has_prev,
        },
    })


def audit(action, resource, resource_id=None, user_id=None):
    db.session.add(AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=request.remote_addr or "unknown",
    ))


def tokens_for(user):
    identity = str(user.id)
    access = create_access_token(identity=identity)
    refresh = create_refresh_token(identity=identity)
    decoded = decode_token(refresh)
    db.session.add(RefreshToken(
        jti=decoded["jti"],
        user_id=user.id,
        expires_at=datetime.fromtimestamp(decoded["exp"], timezone.utc),
    ))
    return {"access_token": access, "refresh_token": refresh, "token_type": "Bearer"}


def current_user_id():
    return int(get_jwt_identity())


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///api.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY", "change-this-secret-in-production"),
        JWT_ACCESS_TOKEN_EXPIRES=900,
        JWT_REFRESH_TOKEN_EXPIRES=2592000,
        PROPAGATE_EXCEPTIONS=False,
    )
    if config:
        app.config.update(config)
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    @app.post("/v1/auth/register")
    def register():
        data, failure = json_body({"email", "password"}, {"email", "password"})
        if failure:
            return failure
        email = validate_email(data["email"])
        details = {}
        if not email:
            details["email"] = "Must be a valid email address"
        if not isinstance(data["password"], str) or len(data["password"]) < 8 or len(data["password"]) > 128:
            details["password"] = "Must be between 8 and 128 characters"
        if details:
            return error("validation_error", "Invalid request data", 422, details)
        if db.session.scalar(select(User).where(User.email == email)):
            return error("email_conflict", "An account with this email already exists", 409)
        user = User(email=email, password_hash=generate_password_hash(data["password"]))
        db.session.add(user)
        db.session.flush()
        audit("create", "user", user.id, user.id)
        db.session.commit()
        return jsonify({"user": user.json()}), 201

    @app.post("/v1/auth/login")
    @limiter.limit("5 per minute")
    def login():
        data, failure = json_body({"email", "password"}, {"email", "password"})
        if failure:
            return failure
        email = validate_email(data["email"])
        if not email or not isinstance(data["password"], str):
            return error("validation_error", "A valid email and password are required", 422)
        user = db.session.scalar(select(User).where(User.email == email))
        if not user or not check_password_hash(user.password_hash, data["password"]):
            return error("invalid_credentials", "Invalid email or password", 401)
        result = tokens_for(user)
        audit("login", "session", user_id=user.id)
        db.session.commit()
        return jsonify(result)

    @app.post("/v1/auth/refresh")
    @jwt_required(refresh=True)
    def refresh():
        claims = get_jwt()
        token = db.session.scalar(select(RefreshToken).where(RefreshToken.jti == claims["jti"]))
        if not token or token.revoked:
            return error("token_revoked", "Refresh token has been revoked", 401)
        user = db.session.get(User, current_user_id())
        if not user:
            return error("user_not_found", "User no longer exists", 401)
        token.revoked = True
        result = tokens_for(user)
        audit("refresh", "session", user_id=user.id)
        db.session.commit()
        return jsonify(result)

    @app.post("/v1/auth/logout")
    @jwt_required(refresh=True)
    def logout():
        claims = get_jwt()
        token = db.session.scalar(select(RefreshToken).where(RefreshToken.jti == claims["jti"]))
        if not token or token.revoked:
            return error("token_revoked", "Refresh token has been revoked", 401)
        token.revoked = True
        audit("logout", "session", user_id=current_user_id())
        db.session.commit()
        return "", 204

    @app.get("/v1/users/me")
    @jwt_required()
    def me():
        user = db.session.get(User, current_user_id())
        if not user:
            return error("user_not_found", "User no longer exists", 404)
        return jsonify({"user": user.json()})

    @app.get("/v1/items")
    @jwt_required()
    def list_items():
        query = select(Item).where(Item.owner_id == current_user_id()).order_by(Item.id)
        return paginated(query, lambda item: item.json())

    @app.post("/v1/items")
    @jwt_required()
    def create_item():
        data, failure = json_body({"name", "description"}, {"name"})
        if failure:
            return failure
        name = data["name"].strip() if isinstance(data["name"], str) else ""
        description = data.get("description", "")
        details = {}
        if not name or len(name) > 120:
            details["name"] = "Must be between 1 and 120 characters"
        if not isinstance(description, str) or len(description) > 1000:
            details["description"] = "Must be a string of at most 1000 characters"
        if details:
            return error("validation_error", "Invalid request data", 422, details)
        item = Item(name=name, description=description, owner_id=current_user_id())
        db.session.add(item)
        db.session.flush()
        audit("create", "item", item.id, current_user_id())
        db.session.commit()
        return jsonify({"item": item.json()}), 201

    @app.get("/v1/items/<int:item_id>")
    @jwt_required()
    def get_item(item_id):
        item = db.session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == current_user_id()))
        if not item:
            return error("not_found", "Item not found", 404)
        return jsonify({"item": item.json()})

    @app.route("/v1/items/<int:item_id>", methods=["PUT", "PATCH"])
    @jwt_required()
    def update_item(item_id):
        required = {"name"} if request.method == "PUT" else set()
        data, failure = json_body({"name", "description"}, required)
        if failure:
            return failure
        if not data:
            return error("validation_error", "At least one field is required", 422)
        item = db.session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == current_user_id()))
        if not item:
            return error("not_found", "Item not found", 404)
        details = {}
        if "name" in data:
            name = data["name"].strip() if isinstance(data["name"], str) else ""
            if not name or len(name) > 120:
                details["name"] = "Must be between 1 and 120 characters"
        if "description" in data and (not isinstance(data["description"], str) or len(data["description"]) > 1000):
            details["description"] = "Must be a string of at most 1000 characters"
        if details:
            return error("validation_error", "Invalid request data", 422, details)
        if "name" in data:
            item.name = name
        if "description" in data:
            item.description = data["description"]
        item.updated_at = datetime.now(timezone.utc)
        audit("update", "item", item.id, current_user_id())
        db.session.commit()
        return jsonify({"item": item.json()})

    @app.delete("/v1/items/<int:item_id>")
    @jwt_required()
    def delete_item(item_id):
        item = db.session.scalar(select(Item).where(Item.id == item_id, Item.owner_id == current_user_id()))
        if not item:
            return error("not_found", "Item not found", 404)
        audit("delete", "item", item.id, current_user_id())
        db.session.delete(item)
        db.session.commit()
        return "", 204

    @app.get("/v1/audit-logs")
    @jwt_required()
    def list_audits():
        query = select(AuditLog).where(AuditLog.user_id == current_user_id()).order_by(AuditLog.id.desc())
        return paginated(query, lambda entry: entry.json())

    @app.get("/v1/health")
    def health():
        return jsonify({"status": "ok"})

    @jwt.unauthorized_loader
    def missing_token(reason):
        return error("authorization_required", "A valid bearer token is required", 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error("invalid_token", "Token is invalid", 401)

    @jwt.expired_token_loader
    def expired_token(header, payload):
        return error("token_expired", "Token has expired", 401)

    @jwt.revoked_token_loader
    def revoked_token(header, payload):
        return error("token_revoked", "Token has been revoked", 401)

    @app.errorhandler(429)
    def rate_limited(exc):
        response, status = error("rate_limit_exceeded", "Too many login attempts; try again later", 429)
        response.headers["Retry-After"] = str(getattr(exc, "retry_after", 60) or 60)
        return response, status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return error(exc.name.lower().replace(" ", "_"), exc.description, exc.code)

    @app.errorhandler(Exception)
    def internal_error(exc):
        db.session.rollback()
        app.logger.exception("Unhandled API error")
        return error("internal_server_error", "An unexpected error occurred", 500)

    with app.app_context():
        db.create_all()
    return app


app = create_app()


if __name__ == "__main__":
    app.run()
