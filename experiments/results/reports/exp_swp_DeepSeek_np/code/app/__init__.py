from flask import Flask
from flask_jwt_extended import JWTManager

from .auth import auth_bp
from .config import Config
from .errors import register_error_handlers
from .extensions import db, jwt
from .items import items_bp
from .rate_limit import RateLimiter


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    db.init_app(app)
    jwt.init_app(app)

    app.login_limiter = RateLimiter(
        max_attempts=app.config.get("RATE_LIMIT_MAX_ATTEMPTS", 5),
        window=app.config.get("RATE_LIMIT_WINDOW", 60),
    )

    app.register_blueprint(auth_bp, url_prefix="/v1")
    app.register_blueprint(items_bp, url_prefix="/v1")

    register_error_handlers(app)
    _register_jwt_handlers(app)

    with app.app_context():
        db.create_all()

    return app


def _register_jwt_handlers(app):
    jwt_manager = JWTManager(app)

    @jwt_manager.unauthorized_loader
    def missing_token(reason):
        return (
            _json_error("unauthorized", reason or "Authentication is required.", 401),
            401,
        )

    @jwt_manager.invalid_token_loader
    def invalid_token(reason):
        return (
            _json_error("invalid_token", reason or "The token is invalid.", 401),
            401,
        )

    @jwt_manager.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return (
            _json_error("token_expired", "The token has expired.", 401),
            401,
        )

    @jwt_manager.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return (
            _json_error("token_revoked", "The token has been revoked.", 401),
            401,
        )

    @jwt_manager.needs_fresh_token_loader
    def needs_fresh(jwt_header, jwt_payload):
        return (
            _json_error("fresh_token_required", "A fresh token is required.", 401),
            401,
        )


def _json_error(code, message, status_code):
    from flask import jsonify

    return jsonify(
        {"error": code, "message": message, "status_code": status_code}
    )
