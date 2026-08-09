from flask import Flask, jsonify

from app.auth import init_auth
from app.config import Config
from app.middleware.audit import init_audit_logging
from app.middleware.rate_limiter import init_rate_limiter
from app.routes.auth_routes import register_routes as register_auth_routes
from app.routes.v1.users import bp as users_v1_bp
from app.routes.v2.users import bp as users_v2_bp
from app.utils.helpers import register_error_handlers


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    init_auth(app)
    init_rate_limiter(app)
    init_audit_logging(app)
    register_error_handlers(app)

    register_auth_routes(bp := _api_blueprint())
    app.register_blueprint(bp)

    app.register_blueprint(users_v1_bp)
    app.register_blueprint(users_v2_bp)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "version": "1.0.0"})

    return app


def _api_blueprint():
    from flask import Blueprint

    return Blueprint("auth", __name__, url_prefix="/api/v1/auth")
