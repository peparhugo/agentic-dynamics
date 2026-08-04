"""Application factory."""
from flask import jsonify

from .config import CONFIGS
from .errors import error_response, register_error_handlers
from .extensions import db, jwt, limiter


def create_app(config_name="dev", config_overrides=None):
    from flask import Flask

    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name])
    if config_overrides:
        app.config.update(config_overrides)

    # Extensions. Flask-Limiter picks up RATELIMIT_DEFAULT /
    # RATELIMIT_STORAGE_URI / RATELIMIT_HEADERS_ENABLED from app.config.
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    # Blueprints (versioned APIs)
    from .api.v1 import bp as api_v1_bp

    app.register_blueprint(api_v1_bp)

    # Error handling
    register_error_handlers(app)
    _register_jwt_error_handlers()

    # Models must be imported before create_all
    from . import models  # noqa: F401

    with app.app_context():
        db.create_all()

    @app.get("/health")
    @limiter.exempt
    def health():
        return jsonify({"status": "ok"})

    return app


def _register_jwt_error_handlers():
    """Make flask-jwt-extended errors use the standard error envelope."""

    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response(401, "unauthorized", reason)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response(401, "invalid_token", reason)

    @jwt.expired_token_loader
    def expired_token(jwt_header, jwt_payload):
        return error_response(401, "token_expired", "Token has expired.")

    @jwt.revoked_token_loader
    def revoked_token(jwt_header, jwt_payload):
        return error_response(401, "token_revoked", "Token has been revoked.")
