from flask import Flask
from .config import BaseConfig
from .extensions import jwt, limiter, audit_logger, init_audit_hooks
from .errors import register_error_handlers


def create_app(config_object: type | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object or BaseConfig)

    # Init extensions
    jwt.init_app(app)
    limiter.init_app(app)
    init_audit_hooks(app)

    # Blueprints (API v1)
    from .auth.routes import bp as auth_bp
    from .items.routes import bp as items_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(items_bp, url_prefix="/api/v1/items")

    register_error_handlers(app)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
