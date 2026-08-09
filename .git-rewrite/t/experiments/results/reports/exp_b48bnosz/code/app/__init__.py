"""Application factory."""
from flask import Flask, jsonify

from .config import get_config
from .extensions import db, jwt, limiter
from .errors import register_error_handlers, register_jwt_error_handlers
from .audit import register_audit_hooks


API_VERSIONS = {"v1": {"status": "stable", "prefix": "/api/v1"}}


def create_app(config_name: str = "default") -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    db.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)

    from .api.v1 import bp as v1_bp

    app.register_blueprint(v1_bp, url_prefix="/api/v1")

    register_error_handlers(app)
    register_jwt_error_handlers(jwt)
    register_audit_hooks(app)

    @app.after_request
    def add_version_header(response):
        response.headers.setdefault("X-API-Version", "v1")
        return response

    @app.route("/api/versions")
    def versions():
        """Version discovery endpoint."""
        return jsonify({"versions": API_VERSIONS, "latest": "v1"})

    with app.app_context():
        db.create_all()

    return app
