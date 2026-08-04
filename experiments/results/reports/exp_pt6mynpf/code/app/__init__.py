"""Application factory."""
from flask import Flask, jsonify

from app.config import CONFIGS
from app.errors import error_response, register_error_handlers
from app.extensions import db, jwt, limiter


def create_app(config_name: str = "development") -> Flask:
    app = Flask(__name__)
    app.config.from_object(CONFIGS[config_name])

    # Extensions
    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    # Consistent JSON errors for JWT failures
    @jwt.unauthorized_loader
    def missing_token(reason):
        return error_response(401, f"Missing or invalid credentials: {reason}")

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return error_response(401, f"Invalid token: {reason}")

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return error_response(401, "Token has expired.", "token_expired")

    # Blueprints (versioned APIs)
    from app.api.v1 import api_v1

    app.register_blueprint(api_v1)

    register_error_handlers(app)

    @app.get("/health")
    @limiter.exempt
    def health():
        return jsonify({"status": "ok", "versions": ["v1"]})

    with app.app_context():
        db.create_all()

    return app
