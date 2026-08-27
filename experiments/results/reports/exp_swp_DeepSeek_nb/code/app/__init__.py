from flask import Flask, jsonify

from .config import Config
from .errors import APIError
from .extensions import db
from .rate_limit import RateLimiter


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    app.extensions["rate_limiter"] = RateLimiter(
        limit=app.config["LOGIN_RATE_LIMIT"],
        window=app.config["LOGIN_RATE_LIMIT_WINDOW"],
    )

    from .auth import auth_bp
    from .items import items_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)

    register_error_handlers(app)

    with app.app_context():
        db.create_all()

    return app


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        return jsonify(err.to_dict()), err.status_code

    @app.errorhandler(404)
    def handle_not_found(err):
        return jsonify({"error": "not_found", "message": "Resource not found"}), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(err):
        return jsonify({"error": "method_not_allowed", "message": "Method not allowed"}), 405

    @app.errorhandler(400)
    def handle_bad_request(err):
        return jsonify({"error": "bad_request", "message": "Bad request"}), 400

    @app.errorhandler(500)
    def handle_internal_error(err):
        return jsonify({"error": "internal_error", "message": "Internal server error"}), 500
