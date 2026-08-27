from flask import Flask, jsonify

from .extensions import db, limiter
from .errors import (
    APIError,
    register_error_handlers,
)


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object("app.config.Config")
    if config_override:
        app.config.update(config_override)

    db.init_app(app)
    limiter.init_app(app)

    from .models import User, RefreshToken, AuditLog, Item  # noqa: F401

    from .auth import auth_bp
    from .items import items_bp
    from .admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/v1/auth")
    app.register_blueprint(items_bp, url_prefix="/v1/items")
    app.register_blueprint(admin_bp, url_prefix="/v1/admin")

    @app.get("/v1/health")
    def health():
        return jsonify({"status": "ok", "version": "v1"})

    register_error_handlers(app)

    return app
