import logging
import os

from flask import Flask, jsonify

from .config import CONFIGS
from .errors import register_error_handlers
from .extensions import db, jwt, limiter


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name])

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    _configure_jwt_errors(app)
    register_error_handlers(app)

    from .api.v1 import api_v1
    app.register_blueprint(api_v1)

    @app.get("/api")
    def api_versions():
        return jsonify({
            "versions": [
                {"version": "v1", "status": "stable", "base_url": "/api/v1"},
            ],
        })

    with app.app_context():
        db.create_all()

    logging.getLogger("audit").setLevel(logging.INFO)
    return app


def _configure_jwt_errors(app):
    """Make Flask-JWT-Extended failures match the API error envelope."""

    def _err(code, message, status):
        return jsonify({"error": {"code": code, "message": message,
                                  "status": status}}), status

    @jwt.unauthorized_loader
    def missing_token(reason):
        return _err("unauthorized", reason, 401)

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return _err("invalid_token", reason, 401)

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return _err("token_expired", "Token has expired", 401)

    @jwt.revoked_token_loader
    def revoked_token(_header, _payload):
        return _err("token_revoked", "Token has been revoked", 401)
